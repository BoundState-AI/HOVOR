"""OpenAI Realtime adapter, driven through a scripted fake transport —
proves the adapter honors the VoiceProvider contract without a key or
network. Live verification happens when OPENAI_API_KEY exists."""

import pytest

from hovor.voice.openai_realtime import OpenAIRealtimeProvider, build_tutor_instructions
from hovor.voice.orchestrator import MissionOrchestrator
from hovor.voice.provider import ProviderError


class FakeTransport:
    def __init__(self):
        self.sent = []
        self.script = []
        self.closed = False

    def send(self, event):
        self.sent.append(event)

    def recv(self):
        return self.script.pop(0)

    def close(self):
        self.closed = True


def _provider_with(script):
    transport = FakeTransport()
    transport.script = list(script)
    provider = OpenAIRealtimeProvider(transport_factory=lambda: transport)
    provider.create_session({})
    return provider, transport


TURN_SCRIPT = [
    {"type": "response.created"},
    {"type": "response.output_text.delta", "delta": "Dobrý deň. "},
    {"type": "response.output_text.delta", "delta": "Ako vám môžem pomôcť?"},
    {"type": "response.function_call_arguments.done", "name": "complete_objective",
     "arguments": '{"objective_id": "greet_formally"}'},
    {"type": "response.done"},
]


def test_turn_roundtrip_assembles_reply():
    provider, transport = _provider_with(TURN_SCRIPT)
    reply = provider.send_text("Dobrý deň", {"mission": {}, "pending_objective": None})
    assert reply.text == "Dobrý deň. Ako vám môžem pomôcť?"
    assert reply.proposed_tool_calls == [
        {"tool": "complete_objective", "objective_id": "greet_formally"}
    ]
    # session.update + item.create + response.create were sent, in order.
    kinds = [e["type"] for e in transport.sent]
    assert kinds == ["session.update", "conversation.item.create", "response.create"]
    assert {e.type for e in reply.events} >= {"final_transcript", "response_started", "response_completed"}


def test_audio_deltas_assemble_into_playable_wav():
    """Two-way voice: audio deltas from the model come back as one base64
    WAV on the reply (client plays it), alongside the text transcript."""
    import base64

    pcm = b"\x00\x01" * 1200  # 0.05s of fake PCM16 @ 24kHz
    half = len(pcm) // 2
    script = [
        {"type": "response.created"},
        {"type": "response.output_audio_transcript.delta", "delta": "Dobrý deň."},
        {"type": "response.output_audio.delta", "delta": base64.b64encode(pcm[:half]).decode()},
        {"type": "response.output_audio.delta", "delta": base64.b64encode(pcm[half:]).decode()},
        {"type": "response.done"},
    ]
    provider, _ = _provider_with(script)
    reply = provider.send_text("Dobrý deň", {"mission": {}, "pending_objective": None})
    assert reply.text == "Dobrý deň."
    wav = base64.b64decode(reply.audio_b64)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert pcm in wav  # payload survives intact


def test_text_only_reply_has_no_audio():
    provider, _ = _provider_with(TURN_SCRIPT)
    reply = provider.send_text("Dobrý deň", {"mission": {}, "pending_objective": None})
    assert reply.audio_b64 is None


def test_error_event_raises_provider_error():
    provider, _ = _provider_with([{"type": "error", "error": {"message": "rate limited"}}])
    with pytest.raises(ProviderError):
        provider.send_text("x", {"mission": {}})


def test_transport_failure_is_provider_error_not_learner_error(db, content):
    """The orchestrator's degradation path works identically for the real
    adapter: transport dies -> degraded session, nothing scored (spec §32)."""

    class DyingTransport(FakeTransport):
        def send(self, event):
            raise ConnectionError("socket closed")

    provider = OpenAIRealtimeProvider(transport_factory=DyingTransport)
    with pytest.raises(ProviderError):
        provider.create_session({})

    # And through the orchestrator with a session that dies mid-mission:
    class DiesOnTurn(FakeTransport):
        def __init__(self):
            super().__init__()
            self.turns = 0

        def send(self, event):
            if event["type"] == "conversation.item.create":
                raise ConnectionError("socket closed")
            super().send(event)

    provider = OpenAIRealtimeProvider(transport_factory=DiesOnTurn)
    provider.create_session({})
    orchestrator = MissionOrchestrator(db, content, provider)
    vs, _ = orchestrator.start(1, "bratislava_arrival")
    result = orchestrator.handle_learner_turn(vs, "Dobrý deň")
    assert result["provider_failure"] is True
    assert vs.state == "degraded_push_to_talk"


def test_missing_key_yields_actionable_provider_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIRealtimeProvider()  # default WebSocket transport
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        provider.create_session({})


def test_instructions_carry_scenario_but_hide_scoring(content):
    mission = content.mission("modra_archive_records")
    text = build_tutor_instructions(
        {"mission": mission, "pending_objective": "explain_ancestor",
         "just_completed": ["greet_formally"], "no_english": True}
    )
    assert "Kováčová" in text                       # persona
    assert "great-grandfather" in text.lower()      # hidden goal steering
    assert "Never reveal" in text                   # objectives stay hidden
    assert "No-English run" in text
    assert "Never invent pronunciation feedback" in text  # spec §2.3
