"""Learner-state ORM: users, per-(item, mode) mastery estimates, attempts,
error observations, learning sessions (spec §13, §29). Content is NOT here —
it lives in versioned JSON (hovor.content) and is referenced by id +
content_version so attempts can be re-scored after content revisions."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hovor.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Retrieval modes (spec §13, §29). A single "word learned = true" field is
# forbidden: each mode is tracked and scheduled independently.
MODES = (
    "recognition_text",
    "recognition_audio",
    "production_prompted",
    "production_spontaneous",
)

# Pronunciation is deliberately NOT a numeric mode (spec §2.3, §10, §34.13).
# Until a calibrated Slovak pronunciation engine exists, the only stored
# statuses are qualitative.
PRONUNCIATION_STATUSES = ("not_assessed", "unknown", "high_confidence_note")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Content settings (spec §22), kept minimal for the slice.
    tutor_strictness: Mapped[str] = mapped_column(String(20), default="normal")
    grammar_depth: Mapped[str] = mapped_column(String(20), default="normal")
    profanity: Mapped[str] = mapped_column(String(20), default="none")

    # Privacy (spec §31): audio is NOT retained unless explicitly opted in,
    # and research use is a separate consent — no hidden voice training.
    retain_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    research_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)


class MasteryEstimate(Base):
    """One row per (user, item, retrieval mode) — the mastery vector of §13.

    Doubles as the review-schedule row (§29): next_review lives here so the
    scheduler can attack the weakest useful mode of each item.
    """

    __tablename__ = "mastery_estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(80), index=True)  # lexeme or skill id
    item_type: Mapped[str] = mapped_column(String(20), default="lexeme")  # lexeme | skill
    mode: Mapped[str] = mapped_column(String(40))  # one of MODES

    strength: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1 recall estimate
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    latency_ema_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    content_version: Mapped[str] = mapped_column(String(60))


class ErrorObservation(Base):
    """Longitudinal error memory (spec §12, §34.8)."""

    __tablename__ = "error_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"), nullable=True)

    error_tag: Mapped[str] = mapped_column(String(80), index=True)  # e.g. diacritic_error
    category: Mapped[str] = mapped_column(String(40))  # taxonomy of §12
    item_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Attempt(Base):
    """Every meaningful attempt, preserved for future rescoring (spec §27)."""

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("learning_sessions.id"), nullable=True)
    voice_session_id: Mapped[int | None] = mapped_column(ForeignKey("voice_sessions.id"), nullable=True)

    exercise_id: Mapped[str] = mapped_column(String(120))  # e.g. "vlak:production_prompted"
    item_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_mode: Mapped[str] = mapped_column(String(20), default="text")  # text | speech

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_response: Mapped[str] = mapped_column(Text)
    normalized_response: Mapped[str] = mapped_column(Text)

    semantic_success: Mapped[bool] = mapped_column(Boolean, default=False)
    target_structure_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hint_count: Mapped[int] = mapped_column(Integer, default=0)
    error_tags: Mapped[list] = mapped_column(JSON, default=list)

    # Provider failure and learner error are separate event classes (spec §32).
    event_class: Mapped[str] = mapped_column(String(30), default="learner")  # learner | provider_failure

    pronunciation_status: Mapped[str] = mapped_column(String(30), default="not_assessed")

    # Speech evidence (spec §8.2, §27, §31): audio kept only under retain_audio
    # consent; a second independent ASR transcript enables disagreement
    # measurement — when transcripts disagree, we don't score (spec §12).
    audio_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secondary_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_disagreement: Mapped[float | None] = mapped_column(Float, nullable=True)

    scoring_version: Mapped[str] = mapped_column(String(60))
    content_version: Mapped[str] = mapped_column(String(60))
    provider: Mapped[str | None] = mapped_column(String(60), nullable=True)

    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)


class XPEvent(Base):
    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    achievement_id: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Event(Base):
    """Observability event log (spec §30): no production AI system without
    traceability. Everything interesting emits one of these."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningSession(Base):
    """One daily gameplay loop instance (spec §5): Phases A–D."""

    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    state: Mapped[str] = mapped_column(String(20), default="active")  # active | completed
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    content_version: Mapped[str] = mapped_column(String(60))
