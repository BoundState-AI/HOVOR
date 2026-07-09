"""Spec §5C / §16.4 / §32 / §34: the Modra archive boss fight, end to end,
driven through the orchestrator with a persistent mock provider."""

import pytest
from sqlalchemy import select

from hovor.models.learner import Attempt, MasteryEstimate
from hovor.services import xp
from hovor.voice.mock_provider import MockVoiceProvider
from hovor.voice.orchestrator import MissionOrchestrator

MISSION = "modra_archive_records"


@pytest.fixture()
def orchestrator(db, content):
    return MissionOrchestrator(db, content, MockVoiceProvider())


def test_full_mission_win(db, content, orchestrator):
    vs, opening = orchestrator.start(1, MISSION)
    assert "Dobrý deň" in opening["slovak"]

    # One utterance can satisfy two objectives (greeting + identity).
    r = orchestrator.handle_learner_turn(vs, "Dobrý deň, volám sa John Novák.")
    assert set(r["objectives_completed_this_turn"]) == {"greet_formally", "state_identity"}
    # Archivist now elicits the ancestor story.
    assert "rodine" in r["tutor_text"] or "hľadáte" in r["tutor_text"]

    r = orchestrator.handle_learner_turn(vs, "Môj prastarý otec sa narodil v Píle, pri Modre.")
    assert r["objectives_completed_this_turn"] == ["explain_ancestor"]

    r = orchestrator.handle_learner_turn(vs, "Narodil sa v roku 1898.")
    assert r["objectives_completed_this_turn"] == ["understand_question"]
    # The archivist now misstates the birthplace (Bratislava) — repair time.
    assert "Bratislave" in r["tutor_text"]

    r = orchestrator.handle_learner_turn(vs, "Nie, nie. Narodil sa v Píle, pri Modre.")
    assert r["objectives_completed_this_turn"] == ["repair_misunderstanding"]

    r = orchestrator.handle_learner_turn(vs, "Kde je ten záznam, prosím?")
    assert r["mission_complete"] is True
    assert r["session_state"] == "completed"
    assert "matrika" in r["tutor_text"] or "archíve" in r["tutor_text"]

    # Mission produced spontaneous-production evidence, not just XP.
    prod = db.scalars(
        select(MasteryEstimate).where(
            MasteryEstimate.user_id == 1,
            MasteryEstimate.mode == "production_spontaneous",
        )
    ).all()
    assert prod and all(p.strength > 0 for p in prod)
    assert xp.total_xp(db, 1) >= xp.BASE_XP["mission_complete"]


def test_alternate_phrasing_also_wins(db, content, orchestrator):
    """Spec §34.10: multiple valid phrasings complete the same mission."""
    vs, _ = orchestrator.start(2, MISSION)
    orchestrator.handle_learner_turn(vs, "dobry den! ja som Peter.")
    orchestrator.handle_learner_turn(vs, "hladam zaznam. moj pradedko sa narodil pri modre")
    orchestrator.handle_learner_turn(vs, "neviem")
    orchestrator.handle_learner_turn(vs, "nie, pri modre, nie v bratislave")
    r = orchestrator.handle_learner_turn(vs, "co potrebujete odo mna?")
    assert r["mission_complete"] is True


def test_hint_ladder_escalates(db, content, orchestrator):
    vs, _ = orchestrator.start(3, MISSION)
    hints = []
    for _ in range(5):
        r = orchestrator.handle_learner_turn(vs, "ehm...")
        hints.append(r["hint"]["level"])
    # Support ladder: repeat_slower → semantic → first_word → show_text → translate
    assert hints == ["repeat_slower", "semantic", "first_word", "show_text", "translate"]
    # Deep hint use logged failure evidence for the objective's lexemes.
    rows = db.scalars(
        select(MasteryEstimate).where(
            MasteryEstimate.user_id == 3, MasteryEstimate.mode == "production_spontaneous"
        )
    ).all()
    assert rows and all(r.strength == 0.0 for r in rows)


def test_provider_failure_is_not_learner_failure(db, content):
    """Spec §32 / §34.11: outage preserves mission state and scores nothing."""
    provider = MockVoiceProvider()
    orchestrator = MissionOrchestrator(db, content, provider)
    vs, _ = orchestrator.start(4, MISSION)
    orchestrator.handle_learner_turn(vs, "Dobrý deň, volám sa Anna.")
    xp_before = xp.total_xp(db, 4)
    completed_before = dict(vs.objective_state)

    provider.update_session({"fail_on_turn": 2})
    r = orchestrator.handle_learner_turn(vs, "Môj prastarý otec sa narodil v Píle.")

    assert r["provider_failure"] is True
    assert r["fallback"] == "push_to_talk"
    assert vs.state == "degraded_push_to_talk"
    assert xp.total_xp(db, 4) == xp_before  # no XP movement
    # No learner attempt was scored for the failed turn.
    attempts = db.scalars(select(Attempt).where(Attempt.user_id == 4)).all()
    assert all(a.event_class == "learner" for a in attempts)
    assert len(attempts) == 2  # only greet + identity from the healthy turn
    # Mission progress from before the outage is intact.
    assert completed_before["greet_formally"]["status"] == "completed"


def test_interruption_is_logged_not_scored(db, content, orchestrator):
    vs, _ = orchestrator.start(5, MISSION)
    result = orchestrator.interrupt(vs)
    assert result["interrupted"] is True
    assert xp.total_xp(db, 5) == 0


def test_no_numeric_pronunciation_score_anywhere(db, content, orchestrator):
    """Spec §2.3 / §34.13: speech attempts carry a status, never a number."""
    vs, _ = orchestrator.start(6, MISSION)
    orchestrator.handle_learner_turn(vs, "Dobrý deň.")
    attempts = db.scalars(select(Attempt).where(Attempt.user_id == 6)).all()
    assert attempts
    for a in attempts:
        assert a.pronunciation_status in ("not_assessed", "unknown", "high_confidence_note")
