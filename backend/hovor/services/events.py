"""Observability (spec §30): a flat event log everything writes to, and the
aggregations /metrics reads from. No production AI system without traceability.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor.models.learner import Attempt, Event
from hovor.models.voice import ConversationTurn, VoiceSession


def log_event(db: Session, kind: str, user_id: int | None = None, payload: dict | None = None) -> None:
    db.add(Event(kind=kind, user_id=user_id, payload=payload or {}))
    db.flush()


def metrics(db: Session) -> dict:
    attempts = db.scalars(select(Attempt)).all()
    learner_attempts = [a for a in attempts if a.event_class == "learner"]
    turns = db.scalars(select(ConversationTurn)).all()
    voice_sessions = db.scalars(select(VoiceSession)).all()
    events = db.scalars(select(Event)).all()

    by_kind: dict[str, int] = {}
    for e in events:
        by_kind[e.kind] = by_kind.get(e.kind, 0) + 1

    disagreements = [
        a.transcript_disagreement for a in attempts if a.transcript_disagreement is not None
    ]
    speech_attempts = [a for a in learner_attempts if a.input_mode == "speech"]

    return {
        "attempts_total": len(learner_attempts),
        "attempts_success_rate": (
            round(sum(1 for a in learner_attempts if a.semantic_success) / len(learner_attempts), 3)
            if learner_attempts else None
        ),
        "speech_attempts": len(speech_attempts),
        "voice_turns": sum(1 for t in turns if t.role == "learner" and t.event_type == "utterance"),
        "interruptions": sum(1 for t in turns if t.event_type == "interruption"),
        "provider_errors": sum(1 for t in turns if t.event_type == "provider_error"),
        "hints_given": sum(1 for t in turns if t.event_type == "hint"),
        "missions": {
            "started": len(voice_sessions),
            "completed": sum(1 for v in voice_sessions if v.state == "completed"),
            "degraded": sum(1 for v in voice_sessions if v.state.startswith("degraded")),
        },
        "transcript_disagreement_avg": (
            round(sum(disagreements) / len(disagreements), 3) if disagreements else None
        ),
        "events_by_kind": by_kind,
    }
