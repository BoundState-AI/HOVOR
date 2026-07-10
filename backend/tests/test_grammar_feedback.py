"""Error taxonomy growth (word order, known-mistake patterns) and the
explanatory debrief (spec §12, §5D): learners get teaching, never raw tags."""

from hovor.models.learner import User
from hovor.services.attempts import submit_exercise_attempt
from hovor.services.debrief import build_debrief
from hovor.services.evaluation import evaluate_production, known_error_tags
from hovor.services.session_composer import compose_session


def _user(db) -> int:
    user = User(name="Grammar")
    db.add(user)
    db.flush()
    return user.id


def test_scrambled_word_order_communicates_but_flags_structure(content):
    lexeme = content.lexeme("dobry_den")
    result = evaluate_production("deň dobrý", lexeme)
    assert result.semantic_success is True
    assert result.target_structure_success is False
    assert result.errors[0].tag == "word_order:dobry_den"


def test_known_mistake_pattern_is_named(content):
    any_item = next(iter(content.repair_items.values()))
    tags = known_error_tags(any_item["broken"], content.repair_items)
    assert tags and tags[0].tag == f"known_error:{any_item['id']}"
    assert tags[0].detail == any_item.get("explanation", "")


def test_failed_attempt_matching_known_trap_carries_the_explanation(db, content):
    uid = _user(db)
    item = next(iter(content.repair_items.values()))
    target = item["lexemes"][0] if item.get("lexemes") else "volam_sa"
    attempt, _ = submit_exercise_attempt(
        db, uid, None, f"{target}:production_prompted", item["broken"], content
    )
    assert attempt.semantic_success is False
    assert any(t.startswith("known_error:") for t in attempt.error_tags)


def test_debrief_explains_instead_of_leaking_tags(db, content):
    uid = _user(db)
    session = compose_session(db, uid, content)
    ex = session.plan["phase_b"][0]["exercise"]
    submit_exercise_attempt(
        db, uid, session.id, ex["exercise_id"], "completely wrong", content
    )
    debrief = build_debrief(db, uid, session.id, content)
    assert debrief["important_errors"], "the miss must surface"
    entry = debrief["important_errors"][0]
    assert entry["explanation"], "every surfaced error teaches something"
    assert entry["label"], "the Slovak word is named, not its internal id"
    # Failed retrievals list Slovak words, not internal ids.
    for word in debrief["failed_retrievals"]:
        assert "_" not in word
