"""HTTP API: users/settings/privacy, session composition, exercise attempts,
voice missions (live + mock), hear-it TTS, speech transcription, and
/health + /metrics. Thin layer — scoring and scheduling live in services/."""

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from hovor.content.loader import ContentBundle, load_content
from hovor.core.db import get_db
from hovor.models.learner import Attempt, LearningSession, MasteryEstimate, User
from hovor.models.voice import VoiceSession
from hovor.schemas import (
    AttemptOut,
    AttemptRequest,
    PrivacyUpdate,
    SessionStartRequest,
    SettingsUpdate,
    UserCreate,
    UserOut,
    VoiceSessionStart,
    VoiceTurnRequest,
)
from hovor.services import events, game, xp
from hovor.services.attempts import submit_exercise_attempt
from hovor.services.debrief import build_debrief
from hovor.services.session_composer import compose_session
from hovor.voice.mock_provider import MockVoiceProvider
from hovor.voice.orchestrator import MissionOrchestrator
from hovor.voice.provider import ProviderError
from hovor.voice.transcribe import (
    MAX_AUDIO_BYTES,
    TranscriptionUnavailable,
    ensure_latin,
    openai_transcribe,
)
from hovor.voice.tts import (
    MAX_TEXT_LEN,
    Synthesizer,
    TTSUnavailable,
    openai_synthesize,
    speakable_strings,
    synthesize_cached,
)

router = APIRouter(prefix="/api/v1")


def get_content() -> ContentBundle:
    return load_content()


def get_synthesizer() -> Synthesizer:
    return openai_synthesize


@router.get("/tts")
def pronounce(
    text: str,
    content: ContentBundle = Depends(get_content),
    synthesizer: Synthesizer = Depends(get_synthesizer),
) -> Response:
    """Pronunciation audio for a known content string (spec §18). Models
    pronunciation only — grading stays absent until Build 5 (§2.3)."""
    text = text.strip()
    if not text or len(text) > MAX_TEXT_LEN:
        raise HTTPException(status_code=400, detail="text is empty or too long")
    if text not in speakable_strings(content):
        raise HTTPException(status_code=404, detail="not a known content string")
    try:
        audio = synthesize_cached(text, synthesizer)
    except TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        # Content strings are versioned and finite: cache hard at the edge
        # and in the browser so each word is synthesized ~once, ever.
        headers={"Cache-Control": "public, max-age=604800"},
    )


def get_transcriber():
    return openai_transcribe


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile,
    transcriber=Depends(get_transcriber),
) -> dict:
    """Push-to-talk speech-to-text (spec §8). The clip is transcribed and
    discarded — never stored (§31)."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="audio too large")
    try:
        text = transcriber(data, audio.filename or "speech.webm",
                           audio.content_type or "audio/webm")
    except TranscriptionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    # Belt over the transcriber's own suspenders: a learner's Slovak must
    # never echo back in Cyrillic, whatever backend produced the text.
    return {"text": ensure_latin(text)}


def _provider_for(name: str):
    # Adapter registry (spec §7). Everything above this line is provider-neutral;
    # a future GPT-Live adapter registers here and nothing else changes.
    if name in ("mock", "mock-0.1"):
        return MockVoiceProvider()
    if name == "openai-realtime":
        from hovor.voice.openai_realtime import OpenAIRealtimeProvider

        return OpenAIRealtimeProvider()  # needs OPENAI_API_KEY at session start
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
def debrief(
    session_id: int,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    session = db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return build_debrief(db, session.user_id, session_id, content)


# -- attempts ----------------------------------------------------------------

def _validate_exercise_id(exercise_id: str, content: ContentBundle) -> None:
    parts = exercise_id.split(":")
    if parts[0] == "repair":
        if len(parts) < 2 or parts[1] not in content.repair_items:
            raise HTTPException(status_code=404, detail=f"unknown repair item: {exercise_id}")
        return
    if parts[0] in ("contrast", "dictation", "rapid"):
        if len(parts) < 2 or parts[1] not in content.lexemes:
            raise HTTPException(status_code=404, detail=f"unknown item: {exercise_id}")
        if parts[0] == "contrast" and (len(parts) < 3 or parts[2] not in content.lexemes):
            raise HTTPException(status_code=404, detail=f"unknown contrast partner: {exercise_id}")
        return
    if parts[0] not in content.lexemes:
        raise HTTPException(status_code=404, detail=f"unknown item: {parts[0]}")


@router.post("/attempts", response_model=AttemptOut)
def submit_attempt(
    body: AttemptRequest,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    _validate_exercise_id(body.exercise_id, content)
    attempt, extras = submit_exercise_attempt(
        db,
        user_id=body.user_id,
        session_id=body.session_id,
        exercise_id=body.exercise_id,
        response=body.response,
        content=content,
        latency_ms=body.latency_ms,
        hint_count=body.hint_count,
        input_mode=body.input_mode,
        audio_reference=body.audio_reference,
        secondary_transcript=body.secondary_transcript,
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
        focus=extras.get("focus", {}),
        achievements=extras.get("achievements", []),
        note=extras.get("note"),
        expected=extras.get("expected"),
        expected_speakable=extras.get("expected_speakable", False),
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
    requested = body.provider_config.get("provider", "mock")
    provider = _provider_for(requested)
    orchestrator = MissionOrchestrator(db, content, provider)
    provider_degraded = False
    try:
        vs, opening = orchestrator.start(
            body.user_id, body.mission_id, body.learning_session_id, body.provider_config,
            no_english=body.no_english,
        )
    except ProviderError:
        # Provider failure is never the learner's problem (§32): start the
        # mission anyway on the deterministic mock and say so.
        db.rollback()
        orchestrator = MissionOrchestrator(db, content, _provider_for("mock"))
        vs, opening = orchestrator.start(
            body.user_id, body.mission_id, body.learning_session_id, {},
            no_english=body.no_english,
        )
        provider_degraded = True
    db.commit()
    return {
        "voice_session_id": vs.id,
        "mission_id": vs.mission_id,
        "provider": vs.provider,
        "provider_degraded": provider_degraded,
        "tutor_text": opening["slovak"],
        "tutor_english": opening["english"],
        "objective_state": vs.objective_state,
    }


def _rebuild_orchestrator(
    vs: VoiceSession, db: Session, content: ContentBundle, provider_config: dict | None = None
) -> MissionOrchestrator:
    # Stateless HTTP slice: recreate the session's OWN provider per request
    # and replay its config. Per-turn reconnect costs latency; a future Voice
    # Session Broker (spec §23.3) holds one live connection per session.
    # Degraded sessions continue on the mock — the mission goes on (§32).
    name = vs.provider if vs.state == "active" else "mock"
    provider = _provider_for(name or "mock")
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
    try:
        orchestrator = _rebuild_orchestrator(vs, db, content, config)
    except ProviderError:
        # Reconnect failed (key gone, network, provider down): degrade the
        # channel, preserve mission state, score nothing (§32, §34.11).
        vs.state = "degraded_push_to_talk"
        db.commit()
        return {
            "provider_failure": True,
            "fallback": "push_to_talk",
            "mission_state_preserved": True,
            "objective_state": vs.objective_state,
            "tutor_text": None,
        }
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


# -- game layer ----------------------------------------------------------------

@router.get("/users/{user_id}/map")
def campaign_map(
    user_id: int,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    return game.map_state(db, user_id, content)


@router.get("/users/{user_id}/streak")
def user_streak(user_id: int, db: Session = Depends(get_db)):
    return game.streak(db, user_id)


@router.get("/users/{user_id}/achievements")
def user_achievements(
    user_id: int,
    db: Session = Depends(get_db),
    content: ContentBundle = Depends(get_content),
):
    return {"achievements": game.achievements_for(db, user_id, content)}


# -- settings & privacy ----------------------------------------------------------

@router.patch("/users/{user_id}/settings")
def update_settings(user_id: int, body: SettingsUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    for field in ("tutor_strictness", "grammar_depth", "profanity"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    db.commit()
    return {"tutor_strictness": user.tutor_strictness, "grammar_depth": user.grammar_depth,
            "profanity": user.profanity}


@router.patch("/users/{user_id}/privacy")
def update_privacy(user_id: int, body: PrivacyUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if body.retain_audio is not None:
        user.retain_audio = body.retain_audio
    if body.research_opt_in is not None:
        user.research_opt_in = body.research_opt_in
    db.commit()
    return {"retain_audio": user.retain_audio, "research_opt_in": user.research_opt_in}


@router.delete("/users/{user_id}/audio")
def delete_my_audio(user_id: int, db: Session = Depends(get_db)):
    """Delete-my-audio (spec §31): strips stored audio references from every
    attempt. Transcripts and scores remain — only the voice goes."""
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    result = db.execute(
        update(Attempt)
        .where(Attempt.user_id == user_id, Attempt.audio_reference.is_not(None))
        .values(audio_reference=None)
    )
    events.log_event(db, "audio_deleted", user_id, {"count": result.rowcount})
    db.commit()
    return {"deleted": result.rowcount}


# -- observability ----------------------------------------------------------------

@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    return events.metrics(db)
