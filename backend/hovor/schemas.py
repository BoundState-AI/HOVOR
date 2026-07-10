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
    # Speech evidence (spec §8.2, §31)
    audio_reference: str | None = None
    secondary_transcript: str | None = None


class AttemptOut(BaseModel):
    attempt_id: int
    semantic_success: bool
    target_structure_success: bool | None
    error_tags: list[str]
    xp_awarded: int
    pronunciation_status: str
    scoring_version: str
    content_version: str
    focus: dict = Field(default_factory=dict)
    achievements: list[dict] = Field(default_factory=list)
    note: str | None = None
    # Corrected form after a miss (spec §12) + whether TTS can pronounce it.
    expected: str | None = None
    expected_speakable: bool = False


class VoiceSessionStart(BaseModel):
    user_id: int
    mission_id: str
    learning_session_id: int | None = None
    provider_config: dict = Field(default_factory=dict)
    no_english: bool = False


class PrivacyUpdate(BaseModel):
    retain_audio: bool | None = None
    research_opt_in: bool | None = None


class SettingsUpdate(BaseModel):
    tutor_strictness: str | None = Field(default=None, pattern="^(gentle|normal|direct|ruthless)$")
    grammar_depth: str | None = Field(default=None, pattern="^(minimal|normal|detailed|nerd)$")
    profanity: str | None = Field(default=None, pattern="^(none|mild|adult|authentic)$")


class VoiceTurnRequest(BaseModel):
    text: str
    # Dev/test affordance: force the mock provider to fail on this turn so
    # clients can exercise the degradation path (spec §32).
    simulate_provider_failure: bool = False
