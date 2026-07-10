"""Pronunciation endpoint: models sound, never grades it (§2.3). Synthesis
is whitelisted to versioned content strings and cached per process."""

from fastapi.testclient import TestClient

from hovor.core.db import get_db
from hovor.main import create_app
from hovor.api.routes import get_synthesizer
from hovor.voice.tts import _audio_cache, speakable_strings

FAKE_MP3 = b"ID3fake-mp3-bytes"


def _client_with_fake_tts(db):
    calls = []

    def fake_synth(text: str) -> bytes:
        calls.append(text)
        return FAKE_MP3

    app = create_app()
    app.dependency_overrides[get_db] = lambda: iter([db])
    app.dependency_overrides[get_synthesizer] = lambda: fake_synth
    return TestClient(app), calls


def test_known_lexeme_returns_cacheable_audio(db):
    _audio_cache.clear()
    client, calls = _client_with_fake_tts(db)
    r = client.get("/api/v1/tts", params={"text": "ahoj"})
    assert r.status_code == 200
    assert r.content == FAKE_MP3
    assert r.headers["content-type"] == "audio/mpeg"
    assert "max-age" in r.headers["cache-control"]
    assert calls == ["ahoj"]


def test_repeat_requests_hit_the_cache(db):
    _audio_cache.clear()
    client, calls = _client_with_fake_tts(db)
    client.get("/api/v1/tts", params={"text": "ahoj"})
    client.get("/api/v1/tts", params={"text": "ahoj"})
    assert calls == ["ahoj"]  # synthesized exactly once


def test_unknown_text_is_refused(db):
    client, calls = _client_with_fake_tts(db)
    assert client.get("/api/v1/tts", params={"text": "hello there"}).status_code == 404
    assert client.get("/api/v1/tts", params={"text": "x" * 300}).status_code == 400
    assert calls == []  # nothing synthesized, nothing billed


def test_mission_lines_and_repairs_are_speakable(content):
    speakable = speakable_strings(content)
    assert "Dobrý deň, prosím?" in speakable          # mission opening line
    mission = content.mission("bratislava_arrival")
    elicit = mission["objectives"][0]["elicit"]["slovak"]
    assert elicit in speakable
    any_repair = next(iter(content.repair_items.values()))
    assert any_repair["broken"] in speakable
