"""Attempt handling: evaluate → record → update mastery → log errors → award XP.

The full attempt record is preserved for future rescoring (spec §27), stamped
with scoring_version and content_version (spec §34.12).
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from hovor import SCORING_VERSION
from hovor.content.loader import ContentBundle
from hovor.models.learner import Attempt
from hovor.services import learner_model, xp
from hovor.services.evaluation import evaluate_production, evaluate_recognition


def submit_exercise_attempt(
    db: Session,
    user_id: int,
    session_id: int | None,
    exercise_id: str,
    response: str,
    content: ContentBundle,
    latency_ms: int | None = None,
    hint_count: int = 0,
    input_mode: str = "text",
) -> Attempt:
    item_id, _, mode = exercise_id.partition(":")
    lexeme = content.lexeme(item_id)

    if mode.startswith("recognition"):
        result = evaluate_recognition(response, lexeme)
    else:
        result = evaluate_production(response, lexeme)

    mastery_before = learner_model.get_or_create_mastery(
        db, user_id, item_id, mode, content.content_version
    )
    was_delayed_review = (
        mastery_before.next_review is not None
        and learner_model._aware(mastery_before.next_review) <= datetime.now(timezone.utc)
        and mastery_before.attempts > 0
    )

    attempt = Attempt(
        user_id=user_id,
        session_id=session_id,
        exercise_id=exercise_id,
        item_id=item_id,
        mode=mode,
        input_mode=input_mode,
        raw_response=response,
        normalized_response=result.normalized_response,
        semantic_success=result.semantic_success,
        target_structure_success=result.target_structure_success,
        latency_ms=latency_ms,
        hint_count=hint_count,
        error_tags=[e.tag for e in result.errors],
        scoring_version=SCORING_VERSION,
        content_version=content.content_version,
        pronunciation_status="not_assessed",
    )
    db.add(attempt)
    db.flush()

    # Hints reduce credit: 2+ hints means retrieval was not demonstrated.
    effective_success = result.semantic_success and hint_count < 2
    learner_model.record_outcome(
        db, user_id, item_id, mode, effective_success, content.content_version, latency_ms
    )
    learner_model.record_errors(db, user_id, attempt.id, result.errors, item_id=item_id)

    if result.semantic_success:
        if was_delayed_review:
            reason = "delayed_review_success"
        elif mode.startswith("recognition"):
            reason = "recognition_success"
        else:
            reason = "prompted_production_success"
        attempt.xp_awarded = xp.award(db, user_id, reason, exercise_id=exercise_id, attempt_id=attempt.id)

    db.flush()
    return attempt
