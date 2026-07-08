"""XP policy (spec §16.1, §17, §34.9).

XP rewards evidence of retrieval and communication. Repeating trivially easy
items decays to zero — XP cannot be farmed. XP is never used as a mastery
signal; mastery lives in MasteryEstimate.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor.core.config import settings
from hovor.models.learner import Attempt, XPEvent, utcnow

BASE_XP = {
    "recognition_success": 2,
    "prompted_production_success": 5,
    "delayed_review_success": 10,
    "mission_objective": 15,
    "spontaneous_production": 15,
    "misunderstanding_repaired": 20,
    "recurring_error_corrected": 10,
    "mission_complete": 40,
}


def _novelty_multiplier(
    db: Session, user_id: int, exercise_id: str, current_attempt_id: int | None
) -> float:
    """Diminishing returns for repeated successes on the same exercise today.
    The attempt being scored right now is excluded — only PRIOR repetitions
    decay the reward."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = db.scalars(
        select(Attempt).where(
            Attempt.user_id == user_id,
            Attempt.exercise_id == exercise_id,
            Attempt.semantic_success == True,  # noqa: E712
            Attempt.timestamp >= since,
        )
    ).all()
    prior = len([a for a in recent if a.id != current_attempt_id])
    decay = settings.xp_novelty_decay
    return decay[prior] if prior < len(decay) else 0.0


def award(
    db: Session,
    user_id: int,
    reason: str,
    exercise_id: str | None = None,
    attempt_id: int | None = None,
) -> int:
    base = BASE_XP.get(reason, 0)
    multiplier = _novelty_multiplier(db, user_id, exercise_id, attempt_id) if exercise_id else 1.0
    amount = int(base * multiplier)
    if amount > 0:
        db.add(
            XPEvent(
                user_id=user_id,
                attempt_id=attempt_id,
                amount=amount,
                reason=reason,
                created_at=utcnow(),
            )
        )
        db.flush()
    return amount


def total_xp(db: Session, user_id: int) -> int:
    rows = db.scalars(select(XPEvent).where(XPEvent.user_id == user_id)).all()
    return sum(r.amount for r in rows)
