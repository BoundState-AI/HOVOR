from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor.content.loader import ContentBundle, load_content
from hovor.core.db import get_db
from hovor.models.learner import LearningSession, MasteryEstimate, User
from hovor.models.voice import VoiceSession
from hovor.schemas import (
    AttemptOut,
    AttemptRequest,
    SessionStartRequest,
    UserCreate,
    UserOut,
    VoiceSessionStart,
    VoiceTurnRequest,
)
from hovor.services import xp
from hovor.services.attempts import submit_exercise_attempt
from hovor.services.debrief import build_debrief
from hovor.services.session_composer import compose_session
from hovor.voice.mock_provider import MockVoiceProvider
from hovor.voice.orchestrator import MissionOrchestrator

router = APIRouter(prefix="/api/v1")


def get_content() -> ContentBundle:
    return load_content()


def _provider_for(name: str) -> MockVoiceProvider:
    # Adapter registry (spec §7). Real adapters (OpenAI Realtime, GPT-Live,
    # Azure, ...) register here without touching anything above the boundary.
    if name in ("mock", "mock-0.1"):
        return MockVoiceProvider()
    raise HTTPException(status_code=400, detail=f"unknown voice provider: {name}")


# -- users -------------------------------------------------------------------

@router.post("/users", response_model=UserOut)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    user = User(name=body.name)
    db.add(user)
    db.commit()
    return UserOut(id=user.id, name=user.name, total_xp=0)


@router.get("/users/{user_id}/profile")
def get_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    mastery = db.scalars(select(MasteryEstimate).where(MasteryEstimate.user_id == user_id)).all()
    return {
        "id": user.id,
        "name": user.name,
        "total_xp": xp.total_xp(db, user_id),
        "mastery": [
            {
                "item_id": m.item_id,
                "mode": m.mode,
                "strength": round(m.strength, 3),
                "attempts": m.attempts,
                "successes": m.successes,
                "next_review": m.next_review.isoformat() if m.next_review else None,
            }
            for m in mastery
        ],
    }


# -- learning sessions ---------------------------------------------------------

@router.post("/learning-sessions")
def start_session(
    body: SessionStartRequest,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    if db.get(User, body.user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    session = compose_session(db, body.user_id, content)
    db.commit()
    return {"session_id": session.id, "plan": session.plan, "content_version": session.content_version}


@router.get("/learning-sessions/{session_id}/debrief")
def debrief(session_id: int, db: Session = Depends(get_db)):
    session = db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return build_debrief(db, session.user_id, session_id)


# -- attempts ----------------------------------------------------------------

@router.post("/attempts", response_model=AttemptOut)
def submit_attempt(
    body: AttemptRequest,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    item_id = body.exercise_id.partition(":")[0]
    if item_id not in content.lexemes:
        raise HTTPException(status_code=404, detail=f"unknown item: {item_id}")
    attempt = submit_exercise_attempt(
        db,
        user_id=body.user_id,
        session_id=body.session_id,
        exercise_id=body.exercise_id,
        response=body.response,
        content=content,
        latency_ms=body.latency_ms,
        hint_count=body.hint_count,
        input_mode=body.input_mode,
    )
    db.commit()
    return AttemptOut(
        attempt_id=attempt.id,
        semantic_success=attempt.semantic_success,
        target_structure_success=attempt.target_structure_success,
        error_tags=attempt.error_tags,
        xp_awarded=attempt.xp_awarded,
        pronunciation_status=attempt.pronunciation_status,
        scoring_version=attempt.scoring_version,
        content_version=attempt.content_version,
    )


# -- voice missions ------------------------------------------------------------

@router.post("/voice-sessions")
def start_voice_session(
    body: VoiceSessionStart,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    if body.mission_id not in content.missions:
        raise HTTPException(status_code=404, detail="unknown mission")
    provider = _provider_for(body.provider_config.get("provider", "mock"))
    orchestrator = MissionOrchestrator(db, content, provider)
    vs, opening = orchestrator.start(
        body.user_id, body.mission_id, body.learning_session_id, body.provider_config
    )
    db.commit()
    return {
        "voice_session_id": vs.id,
        "mission_id": vs.mission_id,
        "provider": vs.provider,
        "tutor_text": opening["slovak"],
        "tutor_english": opening["english"],
        "objective_state": vs.objective_state,
    }


def _rebuild_orchestrator(
    vs: VoiceSession, db: Session, content: ContentBundle, provider_config: dict | None = None
) -> MissionOrchestrator:
    # Stateless HTTP slice: recreate the provider per request and replay its
    # config. A real deployment holds a live provider connection per session
    # in the Voice Session Broker (spec §23.3).
    provider = _provider_for("mock")
    provider.create_session(provider_config or {})
    return MissionOrchestrator(db, content, provider)


@router.post("/voice-sessions/{voice_session_id}/turns")
def voice_turn(
    voice_session_id: int,
    body: VoiceTurnRequest,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    vs = db.get(VoiceSession, voice_session_id)
    if vs is None:
        raise HTTPException(status_code=404, detail="voice session not found")
    if vs.state not in ("active", "degraded_push_to_talk", "degraded_text"):
        raise HTTPException(status_code=409, detail=f"session is {vs.state}")
    config = {"fail_on_turn": 1} if body.simulate_provider_failure else {}
    orchestrator = _rebuild_orchestrator(vs, db, content, config)
    result = orchestrator.handle_learner_turn(vs, body.text)
    db.commit()
    return result


@router.post("/voice-sessions/{voice_session_id}/interrupt")
def voice_interrupt(
    voice_session_id: int,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    vs = db.get(VoiceSession, voice_session_id)
    if vs is None:
        raise HTTPException(status_code=404, detail="voice session not found")
    orchestrator = _rebuild_orchestrator(vs, db, content)
    result = orchestrator.interrupt(vs)
    db.commit()
    return result
