"""Attempt handling: evaluate → record → update mastery → log errors → award XP.

Exercise id grammar (spec §18 exercise types):
    "<lexeme>:<mode>"        read_translate / listen_select / concept_retrieve
    "dictation:<lexeme>"     listen_type   — hear Slovak, type it exactly
    "contrast:<a>:<b>"       minimal_contrast — meaning of <a>, distractor <b>
    "repair:<item>"          error_repair  — produce the corrected sentence
    "rapid:<lexeme>"         rapid_recall  — concept_retrieve, 3 s budget

Full attempt records are preserved for future rescoring (spec §27), stamped
with scoring_version and content_version (spec §34.12).
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor import SCORING_VERSION
from hovor.content.loader import ContentBundle
from hovor.models.learner import Attempt, ErrorObservation, User
from hovor.services import game, learner_model, xp
from hovor.services.events import log_event
from hovor.services.evaluation import (
    EvaluationResult,
    evaluate_contrast,
    evaluate_production,
    evaluate_recognition,
    evaluate_repair,
    word_disagreement,
)

# Above this, the two transcripts disagree enough that scoring would be a
# guess. "Let's not score it" is a feature, not a failure (spec §12).
DISAGREEMENT_THRESHOLD = 0.5

RAPID_RECALL_BUDGET_MS = 3000


def _evaluate(exercise_id: str, response: str, content: ContentBundle):
    """Returns (result, mastery_targets: list[(item_id, mode)], item_id, mode)."""
    parts = exercise_id.split(":")

    if parts[0] == "repair":
        item = content.repair_items[parts[1]]
        result = evaluate_repair(response, item)
        targets = [(lex, "production_prompted") for lex in item.get("lexemes", [])]
        return result, targets, parts[1], "production_prompted"

    if parts[0] == "contrast":
        target, partner = content.lexeme(parts[1]), content.lexeme(parts[2])
        result = evaluate_contrast(response, target, partner)
        return result, [(target.id, "recognition_text")], target.id, "recognition_text"

    if parts[0] == "dictation":
        lexeme = content.lexeme(parts[1])
        result = evaluate_production(response, lexeme)  # exact Slovak expected
        return result, [(lexeme.id, "recognition_audio")], lexeme.id, "recognition_audio"

    if parts[0] == "rapid":
        lexeme = content.lexeme(parts[1])
        result = evaluate_production(response, lexeme)
        return result, [(lexeme.id, "production_prompted")], lexeme.id, "production_prompted"

    item_id, _, mode = exercise_id.partition(":")
    lexeme = content.lexeme(item_id)
    if mode.startswith("recognition"):
        result = evaluate_recognition(response, lexeme)
    else:
        result = evaluate_production(response, lexeme)
    return result, [(item_id, mode)], item_id, mode


def _focus_state(db: Session, user_id: int, session_id: int | None) -> dict:
    """Focus meter (spec §16.3): mistakes are learning evidence, not
    punishable offenses. Repeated failure triggers support, never a penalty."""
    if session_id is None:
        return {"state": "ok"}
    recent = db.scalars(
        select(Attempt)
        .where(Attempt.user_id == user_id, Attempt.session_id == session_id,
               Attempt.event_class == "learner")
        .order_by(Attempt.id.desc())
        .limit(4)
    ).all()
    consecutive_failures = 0
    for a in recent:
        if a.semantic_success:
            break
        consecutive_failures += 1
    if consecutive_failures >= 3:
        return {"state": "overloaded",
                "advice": "Switch to an easier item or take a break — this is a signal, not a score."}
    if consecutive_failures == 2:
        return {"state": "strained", "advice": "One concept at a time. Slow down."}
    return {"state": "ok"}


def _maybe_resolve_recurring(
    db: Session, user_id: int, item_id: str, mode: str, content: ContentBundle
) -> list[dict]:
    """Two clean successes in a row on an item with a recurring error resolve
    it: XP, 'Again?' achievement, and the error stops haunting the debrief."""
    unresolved = db.scalars(
        select(ErrorObservation).where(
            ErrorObservation.user_id == user_id,
            ErrorObservation.item_id == item_id,
            ErrorObservation.resolved == False,  # noqa: E712
        )
    ).all()
    tags = {e.error_tag for e in unresolved}
    recurring_tags = {t for t in tags if sum(1 for e in unresolved if e.error_tag == t) >= 3}
    if not recurring_tags:
        return []

    last_two = db.scalars(
        select(Attempt)
        .where(Attempt.user_id == user_id, Attempt.item_id == item_id, Attempt.mode == mode,
               Attempt.event_class == "learner")
        .order_by(Attempt.id.desc())
        .limit(2)
    ).all()
    if len(last_two) < 2 or not all(a.semantic_success and not a.error_tags for a in last_two):
        return []

    for obs in unresolved:
        if obs.error_tag in recurring_tags:
            obs.resolved = True
    xp.award(db, user_id, "recurring_error_corrected")
    log_event(db, "recurring_error_resolved", user_id, {"item_id": item_id, "tags": sorted(recurring_tags)})
    return game.check_recurring_resolved(db, user_id, content)


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
    audio_reference: str | None = None,
    secondary_transcript: str | None = None,
) -> tuple[Attempt, dict]:
    result, targets, item_id, mode = _evaluate(exercise_id, response, content)

    # Independent-ASR agreement gate (spec §8.2, §12): if two transcripts of
    # the same speech disagree badly, refuse to score rather than guess.
    disagreement = None
    scoring_blocked = False
    if secondary_transcript is not None and input_mode == "speech":
        disagreement = word_disagreement(response, secondary_transcript)
        scoring_blocked = disagreement > DISAGREEMENT_THRESHOLD

    user = db.get(User, user_id)
    keep_audio = bool(user and user.retain_audio)

    mastery_before = learner_model.get_or_create_mastery(
        db, user_id, targets[0][0], targets[0][1], content.content_version
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
        semantic_success=result.semantic_success and not scoring_blocked,
        target_structure_success=None if scoring_blocked else result.target_structure_success,
        latency_ms=latency_ms,
        hint_count=hint_count,
        error_tags=(["transcript_disagreement"] if scoring_blocked else [e.tag for e in result.errors]),
        scoring_version=SCORING_VERSION,
        content_version=content.content_version,
        pronunciation_status="unknown" if input_mode == "speech" else "not_assessed",
        audio_reference=audio_reference if keep_audio else None,
        secondary_transcript=secondary_transcript,
        transcript_disagreement=disagreement,
    )
    db.add(attempt)
    db.flush()
    log_event(db, "attempt_submitted", user_id,
              {"exercise_id": exercise_id, "success": attempt.semantic_success})

    achievements: list[dict] = []
    if scoring_blocked:
        # No mastery movement, no errors, no XP — uncertainty is not evidence.
        feedback = ("I'm not certain whether that was you or the transcription. "
                    "Let's not score it.")
        return attempt, {"focus": _focus_state(db, user_id, session_id),
                         "achievements": achievements, "note": feedback}

    # Hints reduce credit: 2+ hints means retrieval was not demonstrated.
    effective_success = result.semantic_success and hint_count < 2
    if exercise_id.startswith("rapid:") and latency_ms is not None:
        effective_success = effective_success and latency_ms <= RAPID_RECALL_BUDGET_MS

    for target_item, target_mode in targets:
        learner_model.record_outcome(
            db, user_id, target_item, target_mode, effective_success,
            content.content_version, latency_ms,
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
        achievements += game.check_after_attempt(db, user_id, attempt, content)
        achievements += _maybe_resolve_recurring(db, user_id, item_id, mode, content)

    db.flush()
    return attempt, {"focus": _focus_state(db, user_id, session_id), "achievements": achievements}
