"""Provider-neutral voice interface (spec §7).

No provider-specific event formats are allowed above this boundary. The
OpenAI Realtime adapter, a future GPT-Live adapter, Azure/Google/ElevenLabs
adapters, and the deterministic mock all speak this contract.

The iOS client mirrors this as a Swift protocol (see docs/ARCHITECTURE.md).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ProviderError(Exception):
    """Raised when the voice provider fails. This is NEVER a learner error
    (spec §32, §34.11) — callers must not score it against the learner."""


@dataclass
class ProviderEvent:
    """Normalized event stream. `type` is one of:
    speech_started | speech_stopped | partial_transcript | final_transcript |
    response_started | audio_delta | response_completed | interruption |
    tool_call | error
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class TutorReply:
    text: str
    english_gloss: str | None = None
    events: list[ProviderEvent] = field(default_factory=list)
    # Tool-call proposals (spec §25): the model proposes, application validates.
    proposed_tool_calls: list[dict] = field(default_factory=list)
    # Spoken tutor reply as a base64 WAV, when the provider produces audio.
    # Not persisted (§31) — it rides the turn response to the client only.
    audio_b64: str | None = None


class VoiceProvider(ABC):
    """Session-scoped conversational voice engine."""

    name: str = "abstract"

    @abstractmethod
    def create_session(self, config: dict[str, Any]) -> None: ...

    @abstractmethod
    def update_session(self, config: dict[str, Any]) -> None: ...

    @abstractmethod
    def send_text(self, text: str, context: dict[str, Any]) -> TutorReply:
        """Send a learner utterance (text or transcript) with bounded session
        context; receive the tutor's reply. Raises ProviderError on failure."""

    @abstractmethod
    def interrupt(self) -> ProviderEvent:
        """Learner barged in — stop speaking immediately."""

    @abstractmethod
    def close(self) -> None: ...
