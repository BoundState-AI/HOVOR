from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hovor.core.db import Base
from hovor.models.learner import utcnow


class VoiceSession(Base):
    """A live voice mission (spec §24). Mission state is owned here, by the
    application — never by the voice provider (spec §6.3, §25)."""

    __tablename__ = "voice_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    learning_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("learning_sessions.id"), nullable=True
    )
    mission_id: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(30), default="active")
    # active | completed | failed | degraded_push_to_talk | degraded_text

    # Objective progress: {objective_id: {"status": "pending|completed", ...}}
    objective_state: Mapped[dict] = mapped_column(JSON, default=dict)
    hint_levels: Mapped[dict] = mapped_column(JSON, default=dict)  # objective_id -> int

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_version: Mapped[str] = mapped_column(String(60))


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    voice_session_id: Mapped[int] = mapped_column(ForeignKey("voice_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # learner | tutor | system
    event_type: Mapped[str] = mapped_column(String(40), default="utterance")
    # utterance | interruption | provider_error | hint | objective_completed
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
