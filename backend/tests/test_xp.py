"""Spec §16.1 / §17 / §34.9: XP rewards evidence and cannot be farmed."""

from hovor.models.learner import Attempt
from hovor.services import xp


def _fake_success(db, user_id, exercise_id):
    attempt = Attempt(
        user_id=user_id,
        exercise_id=exercise_id,
        raw_response="x",
        normalized_response="x",
        semantic_success=True,
        scoring_version="t",
        content_version="t",
    )
    db.add(attempt)
    db.flush()
    return attempt


def test_xp_decays_on_repetition(db):
    amounts = []
    for _ in range(4):
        attempt = _fake_success(db, 1, "ahoj:recognition_text")
        amounts.append(
            xp.award(db, 1, "recognition_success", exercise_id="ahoj:recognition_text", attempt_id=attempt.id)
        )
    assert amounts[0] > amounts[1] > 0
    assert amounts[3] == 0  # farming the same easy item yields nothing


def test_production_beats_recognition(db):
    recognition = xp.award(db, 1, "recognition_success", exercise_id="a:recognition_text")
    production = xp.award(db, 1, "spontaneous_production", exercise_id="b:production_spontaneous")
    assert production > recognition


def test_delayed_review_is_high_value(db):
    assert xp.BASE_XP["delayed_review_success"] > xp.BASE_XP["recognition_success"]
    assert xp.BASE_XP["misunderstanding_repaired"] > xp.BASE_XP["prompted_production_success"]
