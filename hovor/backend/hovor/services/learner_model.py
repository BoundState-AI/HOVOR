"""Persistent learner model + review scheduling (spec §13, §28, §29).

Transparent and rule-based by design (spec §28): every update is inspectable.
Each (item, mode) pair has its own strength and its own review schedule —
recognizing a word is not the same capability as retrieving it while speaking.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor.models.learner import MODES, ErrorObservation, MasteryEstimate, utcnow

# Strength update rates. Failure hits harder than success helps — forgetting
# evidence is strong evidence.
LEARN_RATE = 0.35
FORGET_FACTOR = 0.5
SLOW_RESPONSE_MS = 6000  # latency above this halves the credit (spec §28)

# Review interval grows with strength (simplified graded-interval schedule).
_INTERVALS = [
    (0.2, timedelta(minutes=10)),
    (0.4, timedelta(hours=8)),
    (0.6, timedelta(days=1)),
    (0.75, timedelta(days=3)),
    (0.9, timedelta(days=7)),
    (1.01, timedelta(days=21)),
]

RECURRING_ERROR_THRESHOLD = 3


def interval_for_strength(strength: float) -> timedelta:
    for ceiling, interval in _INTERVALS:
        if strength < ceiling:
            return interval
    return _INTERVALS[-1][1]


def get_or_create_mastery(
    db: Session, user_id: int, item_id: str, mode: str, content_version: str, item_type: str = "lexeme"
) -> MasteryEstimate:
    row = db.scalar(
        select(MasteryEstimate).where(
            MasteryEstimate.user_id == user_id,
            MasteryEstimate.item_id == item_id,
            MasteryEstimate.mode == mode,
        )
    )
    if row is None:
        row = MasteryEstimate(
            user_id=user_id,
            item_id=item_id,
            item_type=item_type,
            mode=mode,
            content_version=content_version,
        )
        db.add(row)
        db.flush()
    return row


def record_outcome(
    db: Session,
    user_id: int,
    item_id: str,
    mode: str,
    success: bool,
    content_version: str,
    latency_ms: int | None = None,
    item_type: str = "lexeme",
) -> MasteryEstimate:
    """Update exactly one retrieval mode. A recognition success never touches
    production strength (spec §2.2, §34.6)."""
    if mode not in MODES:
        raise ValueError(f"unknown retrieval mode: {mode}")

    row = get_or_create_mastery(db, user_id, item_id, mode, content_version, item_type)
    row.attempts += 1
    row.last_seen = utcnow()

    if latency_ms is not None:
        row.latency_ema_ms = (
            latency_ms if row.latency_ema_ms is None else 0.7 * row.latency_ema_ms + 0.3 * latency_ms
        )

    if success:
        row.successes += 1
        credit = LEARN_RATE
        if latency_ms is not None and latency_ms > SLOW_RESPONSE_MS:
            credit *= 0.5  # slow retrieval is weak retrieval
        row.strength = min(1.0, row.strength + credit * (1.0 - row.strength))
    else:
        row.strength = max(0.0, row.strength * FORGET_FACTOR)

    # Failure makes the item due immediately — the next retrieval ambush
    # attacks it; success spaces it out (spec §34.7).
    delay = interval_for_strength(row.strength) if success else timedelta(0)
    row.next_review = utcnow() + delay
    db.flush()
    return row


def due_reviews(db: Session, user_id: int, limit: int) -> list[MasteryEstimate]:
    """Items near the forgetting boundary, weakest first (spec §5 Phase A).

    Attacks the weakest useful mode of each item: one row per item, the row
    with the lowest strength among those due or never-scheduled.
    """
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(MasteryEstimate)
        .where(MasteryEstimate.user_id == user_id)
        .order_by(MasteryEstimate.strength.asc())
    ).all()

    by_item: dict[str, MasteryEstimate] = {}
    for row in rows:
        due = row.next_review is None or _aware(row.next_review) <= now
        if due and row.item_id not in by_item:
            by_item[row.item_id] = row
    return list(by_item.values())[:limit]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def record_errors(
    db: Session, user_id: int, attempt_id: int | None, errors: list, item_id: str | None = None
) -> list[str]:
    """Persist error observations; return tags that just became recurring."""
    newly_recurring = []
    for err in errors:
        db.add(
            ErrorObservation(
                user_id=user_id,
                attempt_id=attempt_id,
                error_tag=err.tag,
                category=err.category,
                item_id=item_id,
                detail=err.detail,
            )
        )
        db.flush()
        count = db.scalars(
            select(ErrorObservation).where(
                ErrorObservation.user_id == user_id,
                ErrorObservation.error_tag == err.tag,
                ErrorObservation.resolved == False,  # noqa: E712
            )
        ).all()
        if len(count) == RECURRING_ERROR_THRESHOLD:
            newly_recurring.append(err.tag)
    return newly_recurring


def recurring_errors(db: Session, user_id: int) -> dict[str, int]:
    rows = db.scalars(
        select(ErrorObservation).where(
            ErrorObservation.user_id == user_id,
            ErrorObservation.resolved == False,  # noqa: E712
        )
    ).all()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.error_tag] = counts.get(r.error_tag, 0) + 1
    return {tag: n for tag, n in counts.items() if n >= RECURRING_ERROR_THRESHOLD}
