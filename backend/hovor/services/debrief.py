"""Phase D debrief (spec §5D): show only useful information, never dump
twelve corrections on the learner after a successful conversation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor.core.config import settings
from hovor.models.learner import Attempt, XPEvent
from hovor.services import learner_model


def build_debrief(db: Session, user_id: int, session_id: int) -> dict:
    attempts = db.scalars(
        select(Attempt).where(Attempt.user_id == user_id, Attempt.session_id == session_id)
    ).all()

    successes = [a for a in attempts if a.semantic_success and a.event_class == "learner"]
    failures = [a for a in attempts if not a.semantic_success and a.event_class == "learner"]

    # One or two important errors, recurring patterns first (spec §12).
    recurring = learner_model.recurring_errors(db, user_id)
    important: list[dict] = []
    seen_tags: set[str] = set()
    for attempt in failures:
        for tag in attempt.error_tags:
            if tag in seen_tags:
                continue
            seen_tags.add(tag)
            important.append({"error_tag": tag, "recurring": tag in recurring, "item_id": attempt.item_id})
    important.sort(key=lambda e: not e["recurring"])
    important = important[: settings.debrief_max_corrections]

    failed_retrievals = sorted(
        {a.item_id for a in failures if a.mode and a.mode.startswith("production") and a.item_id}
    )

    xp_rows = db.scalars(select(XPEvent).where(XPEvent.user_id == user_id)).all()
    session_attempt_ids = {a.id for a in attempts}
    session_xp = sum(x.amount for x in xp_rows if x.attempt_id in session_attempt_ids or x.attempt_id is None)

    return {
        "what_worked": {
            "successful_attempts": len(successes),
            "items": sorted({a.item_id for a in successes if a.item_id}),
        },
        "important_errors": important,
        "failed_retrievals": failed_retrievals,
        # Pronunciation feedback appears only with strong evidence (spec §10.2);
        # the rule-based slice never has strong evidence, so this stays empty.
        "pronunciation_notes": [],
        "xp": session_xp,
        "next_review_implication": (
            "Failed items return within minutes; solid items are spaced out."
            if failed_retrievals
            else "Everything held — intervals extended."
        ),
    }
