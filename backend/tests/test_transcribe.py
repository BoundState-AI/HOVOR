"""Push-to-talk transcription endpoint: transcribe and discard (§31)."""

from fastapi.testclient import TestClient

from hovor.core.db import get_db
from hovor.main import create_app
from hovor.api.routes import get_transcriber
from hovor.voice.transcribe import MAX_AUDIO_BYTES, TranscriptionUnavailable


def _client(db, transcriber):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: iter([db])
    app.dependency_overrides[get_transcriber] = lambda: transcriber
    return TestClient(app)


def test_clip_comes_back_as_slovak_text(db):
    seen = {}

    def fake(audio: bytes, filename: str, content_type: str) -> str:
        seen["args"] = (audio, filename, content_type)
        return "Dobrý deň, prosím si lístok."

    client = _client(db, fake)
    r = client.post(
        "/api/v1/transcribe",
        files={"audio": ("speech.webm", b"fake-opus-bytes", "audio/webm")},
    )
    assert r.status_code == 200
    assert r.json() == {"text": "Dobrý deň, prosím si lístok."}
    assert seen["args"] == (b"fake-opus-bytes", "speech.webm", "audio/webm")


def test_empty_and_oversized_clips_are_refused(db):
    calls = []
    client = _client(db, lambda *a: calls.append(a) or "x")
    empty = client.post("/api/v1/transcribe", files={"audio": ("s.webm", b"", "audio/webm")})
    assert empty.status_code == 400
    huge = client.post(
        "/api/v1/transcribe",
        files={"audio": ("s.webm", b"x" * (MAX_AUDIO_BYTES + 1), "audio/webm")},
    )
    assert huge.status_code == 413
    assert calls == []  # nothing hit the paid backend


def test_backend_down_is_503_not_500(db):
    def dead(*args):
        raise TranscriptionUnavailable("no key")

    client = _client(db, dead)
    r = client.post(
        "/api/v1/transcribe",
        files={"audio": ("s.webm", b"bytes", "audio/webm")},
    )
    assert r.status_code == 503
