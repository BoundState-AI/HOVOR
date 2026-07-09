"""OpenAI Realtime adapter (spec §6.2, §7).

Speaks the provider-neutral VoiceProvider contract. The wire protocol lives
behind an injectable Transport so:
  - unit tests drive the adapter with a scripted FakeTransport (no key, no net)
  - the WebSocket transport is swappable for WebRTC later
  - a future GPT-Live adapter reuses the instruction builder unchanged

The adapter receives bounded per-turn context from the orchestrator and
returns proposals. It owns no persistent truth (spec §24, §25).
"""

import json
import os
from typing import Any, Protocol

from hovor.voice.provider import ProviderError, ProviderEvent, TutorReply, VoiceProvider

REALTIME_URL = "wss://api.openai.com/v1/realtime"
DEFAULT_MODEL = "gpt-realtime"


class Transport(Protocol):
    def send(self, event: dict) -> None: ...
    def recv(self) -> dict: ...
    def close(self) -> None: ...


class WebSocketTransport:
    """Synchronous WebSocket transport. Requires the `websockets` package and
    OPENAI_API_KEY. Import and connection are deferred so the adapter can be
    constructed (and tested) without either."""

    def __init__(self, model: str, api_key: str | None = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ProviderError(
                "OPENAI_API_KEY is not set — the OpenAI Realtime adapter needs it. "
                "Use provider 'mock' for offline development."
            )
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise ProviderError(
                "the 'websockets' package is required for the OpenAI Realtime "
                "adapter: pip install websockets"
            ) from exc
        self._ws = connect(
            f"{REALTIME_URL}?model={model}",
            additional_headers={"Authorization": f"Bearer {key}"},
        )

    def send(self, event: dict) -> None:
        self._ws.send(json.dumps(event))

    def recv(self) -> dict:
        return json.loads(self._ws.recv())

    def close(self) -> None:
        self._ws.close()


def build_tutor_instructions(context: dict[str, Any]) -> str:
    """Per-turn system instructions from bounded session context. Shared by
    any LLM-backed provider — the mission stays hidden-objective-driven and
    the correction policy (spec §12) rides along."""
    mission = context.get("mission", {})
    character = mission.get("character", {})
    pending = context.get("pending_objective")
    objectives = {o["id"]: o for o in mission.get("objectives", [])}

    lines = [
        f"You are {character.get('name', 'a Slovak tutor')}, "
        f"{character.get('role', 'helping an English speaker learn Slovak')}.",
        f"Register: {character.get('register', 'neutral')}. Speak Slovak. "
        "Keep replies to one or two short sentences a beginner can parse.",
        "You are also a language tutor playing a scenario. Never reveal that "
        "objectives or scoring exist. Never invent pronunciation feedback.",
        "Correction policy: fix communication-blocking errors immediately by "
        "restating correctly; let harmless errors pass to preserve flow.",
    ]
    if context.get("just_completed"):
        done = ", ".join(context["just_completed"])
        lines.append(f"The learner just accomplished: {done}. Acknowledge naturally, in character.")
    if context.get("mission_complete"):
        lines.append("The scenario is complete. Close warmly, in character, in Slovak.")
    elif pending and pending in objectives:
        goal = objectives[pending].get("hidden_goal", "")
        lines.append(f"Steer the conversation so the learner must: {goal} Do not say this outright.")
    if context.get("hint"):
        lines.append(f"The learner is stuck. Offer this support naturally: {context['hint']['text']}")
    if context.get("no_english"):
        lines.append("No-English run: do not use English under any circumstances.")
    return "\n".join(lines)


class OpenAIRealtimeProvider(VoiceProvider):
    name = "openai-realtime"

    def __init__(self, transport_factory=None, model: str = DEFAULT_MODEL):
        self._model = model
        self._factory = transport_factory or (lambda: WebSocketTransport(model))
        self._transport: Transport | None = None
        self._config: dict[str, Any] = {}

    def create_session(self, config: dict[str, Any]) -> None:
        self._config = config
        try:
            self._transport = self._factory()
            # GA realtime wire format (2025-08+): session.type is required,
            # modalities → output_modalities, voice/transcription live under audio.
            self._transport.send(
                {
                    "type": "session.update",
                    "session": {
                        "type": "realtime",
                        "output_modalities": ["audio"],
                        "audio": {
                            "input": {"transcription": {"model": "gpt-4o-transcribe", "language": "sk"}},
                            "output": {"voice": config.get("voice", "marin")},
                        },
                    },
                }
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"realtime session setup failed: {exc}") from exc

    def update_session(self, config: dict[str, Any]) -> None:
        self._config.update(config)

    def send_text(self, text: str, context: dict[str, Any]) -> TutorReply:
        if self._transport is None:
            raise ProviderError("session not created")
        try:
            self._transport.send(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    },
                }
            )
            self._transport.send(
                {
                    "type": "response.create",
                    "response": {"instructions": build_tutor_instructions(context)},
                }
            )
            return self._collect_response(text)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"realtime turn failed: {exc}") from exc

    def _collect_response(self, learner_text: str) -> TutorReply:
        events: list[ProviderEvent] = [ProviderEvent("final_transcript", {"text": learner_text})]
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        while True:
            event = self._transport.recv()
            etype = event.get("type", "")
            if etype == "response.created":
                events.append(ProviderEvent("response_started"))
            elif etype in ("response.output_text.delta", "response.text.delta"):
                text_parts.append(event.get("delta", ""))
            elif etype == "response.output_audio_transcript.delta":
                text_parts.append(event.get("delta", ""))
            elif etype == "response.output_audio.delta":
                events.append(ProviderEvent("audio_delta", {"size": len(event.get("delta", ""))}))
            elif etype == "response.function_call_arguments.done":
                try:
                    args = json.loads(event.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({"tool": event.get("name", ""), **args})
            elif etype == "response.done":
                events.append(ProviderEvent("response_completed"))
                break
            elif etype == "error":
                raise ProviderError(f"realtime error: {event.get('error', event)}")
        return TutorReply(
            text="".join(text_parts).strip(),
            english_gloss=None,  # a real model speaks Slovak; gloss is a client concern
            events=events,
            proposed_tool_calls=tool_calls,
        )

    def interrupt(self) -> ProviderEvent:
        if self._transport is None:
            return ProviderEvent("interruption", {"stopped_mid_response": False})
        try:
            self._transport.send({"type": "response.cancel"})
        except Exception as exc:
            raise ProviderError(f"interrupt failed: {exc}") from exc
        return ProviderEvent("interruption", {"stopped_mid_response": True})

    def close(self) -> None:
        if self._transport is not None:
            try:
                self._transport.close()
            finally:
                self._transport = None
