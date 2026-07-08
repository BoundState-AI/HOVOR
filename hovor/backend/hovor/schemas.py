from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class UserOut(BaseModel):
    id: int
    name: str
    total_xp: int


class MasteryOut(BaseModel):
    item_id: str
    mode: str
    strength: float
    attempts: int
    successes: int
    next_review: str | None


class SessionStartRequest(BaseModel):
    user_id: int


class AttemptRequest(BaseModel):
    user_id: int
    session_id: int | None = None
    exercise_id: str
    response: str
    latency_ms: int | None = None
    hint_count: int = 0
    input_mode: str = "text"


class AttemptOut(BaseModel):
    attempt_id: int
    semantic_success: bool
    target_structure_success: bool | None
    error_tags: list[str]
    xp_awarded: int
    pronunciation_status: str
    scoring_version: str
    content_version: str


class VoiceSessionStart(BaseModel):
    user_id: int
    mission_id: str
    learning_session_id: int | None = None
    provider_config: dict = Field(default_factory=dict)


class VoiceTurnRequest(BaseModel):
    text: str
    # Dev/test affordance: force the mock provider to fail on this turn so
    # clients can exercise the degradation path (spec §32).
    simulate_provider_failure: bool = False
