"""Game layer (spec §4, §16, §17): map unlocks, achievements, no-English runs,
strictness, English-dependence tracking."""

import pytest
from sqlalchemy import select

from hovor.models.learner import ErrorObservation, User, XPEvent
from hovor.services import game, xp
from hovor.voice.mock_provider import MockVoiceProvider
from hovor.voice.orchestrator import MissionOrchestrator


@pytest.fixture()
def orchestrator(db, content):
    return MissionOrchestrator(db, content, MockVoiceProvider())


def _make_user(db, name="Tester", strictness="normal"):
    user = User(name=name, tutor_strictness=strictness)
    db.add(user)
    db.flush()
    return user


def _win_bratislava(orchestrator, vs):
    orchestrator.handle_learner_turn(vs, "Dobrý deň. Prosím si lístok do Pezinka.")
    orchestrator.handle_learner_turn(vs, "Jednosmerný, prosím.")
    orchestrator.handle_learner_turn(vs, "Dnes.")
    # Repair completes the last required objective; thanks rides along.
    return orchestrator.handle_learner_turn(vs, "Nie, do Pezinka! Ďakujem, dovidenia.")


def test_map_unlock_progression(db, content, orchestrator):
    user = _make_user(db)
    state = game.map_state(db, user.id, content)
    by_id = {r["id"]: r for r in state["regions"]}
    assert by_id["bratislava"]["unlocked"] is True
    assert by_id["svaty_jur"]["unlocked"] is False  # gated on arrival mission
    assert by_id["modra"]["unlocked"] is False

    vs, _ = orchestrator.start(user.id, "bratislava_arrival")
    r = _win_bratislava(orchestrator, vs)
    assert r["mission_complete"] is True

    state = game.map_state(db, user.id, content)
    by_id = {r["id"]: r for r in state["regions"]}
    assert by_id["svaty_jur"]["unlocked"] is True
    assert by_id["modra"]["unlocked"] is False  # needs the family visit first
    # Beaten missions become replayable as no-English runs (spec §16.5).
    assert by_id["bratislava"]["missions"][0]["no_english_available"] is True


def test_next_mission_follows_campaign(db, content, orchestrator):
    user = _make_user(db)
    assert game.next_mission(db, user.id, content) == "bratislava_arrival"
    vs, _ = orchestrator.start(user.id, "bratislava_arrival")
    _win_bratislava(orchestrator, vs)
    assert game.next_mission(db, user.id, content) == "svaty_jur_family"


def test_mission_achievements(db, content, orchestrator):
    user = _make_user(db)
    vs, _ = orchestrator.start(user.id, "bratislava_arrival")
    r = _win_bratislava(orchestrator, vs)
    granted = {a["id"] for a in r["achievements"]}
    assert "survived_bratislava" in granted
    assert "stop_translating" in granted        # zero English turns
    assert "they_understood_you" in granted      # zero hints
    # Idempotent: replay does not re-grant.
    vs2, _ = orchestrator.start(user.id, "bratislava_arrival")
    r2 = _win_bratislava(orchestrator, vs2)
    assert not {a["id"] for a in r2["achievements"]} & granted


def test_english_fallback_tracked_and_blocks_stop_translating(db, content, orchestrator):
    user = _make_user(db)
    vs, _ = orchestrator.start(user.id, "bratislava_arrival")
    r = orchestrator.handle_learner_turn(vs, "Sorry, I don't know what you want")
    assert r["english_fallback"] is True
    assert vs.english_turns == 1
    obs = db.scalars(
        select(ErrorObservation).where(
            ErrorObservation.user_id == user.id,
            ErrorObservation.error_tag == "english_dependence",
        )
    ).all()
    assert len(obs) == 1

    final = _win_bratislava(orchestrator, vs)
    granted = {a["id"] for a in final["achievements"]}
    assert "stop_translating" not in granted


def test_no_english_run_charges_for_deep_hints(db, content):
    user = _make_user(db)
    orchestrator = MissionOrchestrator(db, content, MockVoiceProvider())
    vs, _ = orchestrator.start(user.id, "bratislava_arrival", no_english=True)
    for _ in range(5):  # descend the whole ladder on the first objective
        orchestrator.handle_learner_turn(vs, "hmm")
    charges = db.scalars(
        select(XPEvent).where(XPEvent.user_id == user.id, XPEvent.reason == "emergency_help")
    ).all()
    assert len(charges) == 2  # show_text + translate rungs
    assert all(c.amount < 0 for c in charges)

    final = _win_bratislava(orchestrator, vs)
    assert "no_english_run" in {a["id"] for a in final["achievements"]}


def test_ruthless_strictness_never_reveals_answer(db, content):
    user = _make_user(db, strictness="ruthless")
    orchestrator = MissionOrchestrator(db, content, MockVoiceProvider())
    vs, _ = orchestrator.start(user.id, "bratislava_arrival")
    hints = [orchestrator.handle_learner_turn(vs, "eh")["hint"]["level"] for _ in range(4)]
    assert hints[0] == "semantic"          # skips repeat_slower
    assert hints[-1] == "first_word"       # capped — never show_text/translate
    assert "show_text" not in hints and "translate" not in hints


def test_streak_counts_consecutive_days(db, content):
    from datetime import datetime, timedelta, timezone

    from hovor.models.learner import Attempt

    user = _make_user(db)
    now = datetime.now(timezone.utc)
    for days_ago in (0, 1, 2):
        db.add(Attempt(
            user_id=user.id, exercise_id="ahoj:recognition_text",
            raw_response="x", normalized_response="x", semantic_success=True,
            scoring_version="t", content_version="t",
            timestamp=now - timedelta(days=days_ago),
        ))
    db.flush()
    s = game.streak(db, user.id)
    assert s["days"] == 3


def test_xp_can_go_negative_only_via_emergency_help(db, content):
    user = _make_user(db)
    db.add(XPEvent(user_id=user.id, amount=-10, reason="emergency_help"))
    db.flush()
    assert xp.total_xp(db, user.id) == -10
