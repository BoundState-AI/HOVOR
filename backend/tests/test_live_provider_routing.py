"""Live-provider routing through the HTTP slice: sessions remember their
provider, turns rebuild it, and every failure degrades per §32 — the mission
never dies with a 500 and nothing is scored against the learner."""

from hovor.models.voice import VoiceSession


def _user(client) -> int:
    return client.post("/api/v1/users", json={"name": "Jana"}).json()["id"]


def test_start_without_key_degrades_to_mock_and_says_so(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    uid = _user(client)
    vs = client.post(
        "/api/v1/voice-sessions",
        json={
            "user_id": uid,
            "mission_id": "bratislava_arrival",
            "provider_config": {"provider": "openai-realtime"},
        },
    ).json()
    assert vs["provider_degraded"] is True
    assert vs["provider"] == "mock-0.1"
    assert vs["tutor_text"]  # mission opened anyway

    # And the mission is fully playable on the fallback.
    turn = client.post(
        f"/api/v1/voice-sessions/{vs['voice_session_id']}/turns",
        json={"text": "Dobrý deň"},
    ).json()
    assert turn["provider_failure"] is False
    assert turn["tutor_text"]


def test_mock_start_reports_no_degradation(client):
    uid = _user(client)
    vs = client.post(
        "/api/v1/voice-sessions",
        json={"user_id": uid, "mission_id": "bratislava_arrival"},
    ).json()
    assert vs["provider_degraded"] is False
    assert vs["provider"] == "mock-0.1"


def test_turn_honors_stored_provider_then_degrades_then_continues(client, db, content, monkeypatch):
    """A live session whose provider can't reconnect: first turn degrades the
    channel (state preserved, unscored), the next turn continues on the mock."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    uid = _user(client)
    mission = content.mission("bratislava_arrival")
    vs = VoiceSession(
        user_id=uid,
        mission_id="bratislava_arrival",
        provider="openai-realtime",
        objective_state={o["id"]: {"status": "pending"} for o in mission["objectives"]},
        hint_levels={},
        content_version=content.content_version,
    )
    db.add(vs)
    db.flush()

    first = client.post(
        f"/api/v1/voice-sessions/{vs.id}/turns", json={"text": "Dobrý deň"}
    ).json()
    assert first["provider_failure"] is True
    assert first["mission_state_preserved"] is True
    assert vs.state == "degraded_push_to_talk"

    second = client.post(
        f"/api/v1/voice-sessions/{vs.id}/turns", json={"text": "Dobrý deň"}
    ).json()
    assert second["provider_failure"] is False
    assert second["tutor_text"]


def test_mock_turns_carry_no_audio(client):
    uid = _user(client)
    vs = client.post(
        "/api/v1/voice-sessions",
        json={"user_id": uid, "mission_id": "bratislava_arrival"},
    ).json()
    turn = client.post(
        f"/api/v1/voice-sessions/{vs['voice_session_id']}/turns",
        json={"text": "Dobrý deň"},
    ).json()
    assert turn["tutor_audio_b64"] is None
