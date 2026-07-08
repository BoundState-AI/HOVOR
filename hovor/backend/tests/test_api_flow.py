"""Spec §34: the whole loop over the API — the way the iOS client will use it.
A new learner starts with zero Slovak, speaks in session one, completes the
Modra archive mission, and gets an honest debrief."""


def test_health_reports_content_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["content_version"] == "ancestry-slice-0.1.0"
    assert body["content_review_status"] == "PENDING_NATIVE_REVIEW"


def test_full_session_loop(client):
    user = client.post("/api/v1/users", json={"name": "Johnny"}).json()
    uid = user["id"]

    # Session composes Phases A–C. Brand-new learner: nothing due, all new.
    session = client.post("/api/v1/learning-sessions", json={"user_id": uid}).json()
    sid = session["session_id"]
    plan = session["plan"]
    assert plan["phase_a"] == []  # no reviews yet — nothing to ambush
    assert len(plan["phase_b"]) == 5  # tightly constrained new material
    # Skill graph orders introduction: stage-0 material comes first.
    first_item = plan["phase_b"][0]["introduce"]
    assert set(first_item["skill_nodes"]) & {"greetings_basic", "survival_phrases", "identity_statements"}
    assert plan["phase_c"]["mission_id"] == "modra_archive_records"

    # Phase B: introduce + immediate production. One success, one failure.
    ex_ok = plan["phase_b"][0]["exercise"]
    slovak_form = plan["phase_b"][0]["introduce"]["slovak"]
    r = client.post(
        "/api/v1/attempts",
        json={"user_id": uid, "session_id": sid, "exercise_id": ex_ok["exercise_id"],
              "response": slovak_form, "latency_ms": 1500},
    ).json()
    assert r["semantic_success"] is True
    assert r["xp_awarded"] > 0
    assert r["scoring_version"] and r["content_version"]  # traceability (§34.12)

    ex_fail = plan["phase_b"][1]["exercise"]
    r = client.post(
        "/api/v1/attempts",
        json={"user_id": uid, "session_id": sid, "exercise_id": ex_fail["exercise_id"],
              "response": "úplne zle", "latency_ms": 4000},
    ).json()
    assert r["semantic_success"] is False

    # Phase C: the voice mission over the API.
    vs = client.post(
        "/api/v1/voice-sessions",
        json={"user_id": uid, "mission_id": "modra_archive_records", "learning_session_id": sid},
    ).json()
    vsid = vs["voice_session_id"]
    assert "Dobrý deň" in vs["tutor_text"]

    def turn(text, **extra):
        return client.post(f"/api/v1/voice-sessions/{vsid}/turns", json={"text": text, **extra}).json()

    turn("Dobrý deň, volám sa Johnny.")
    turn("Môj prastarý otec sa narodil v Píle pri Modre.")

    # Interruption mid-mission is allowed and unscored.
    assert client.post(f"/api/v1/voice-sessions/{vsid}/interrupt").json()["interrupted"]

    # Provider outage mid-mission: state preserved, channel degraded (§32).
    outage = turn("Narodil sa v roku 1898.", simulate_provider_failure=True)
    assert outage["provider_failure"] is True
    assert outage["mission_state_preserved"] is True

    # Learner continues in degraded mode and still wins.
    r = turn("Narodil sa v roku 1898.")
    assert r["provider_failure"] is False
    turn("Nie, narodil sa v Píle, nie v Bratislave.")
    final = turn("Kde je ten záznam?")
    assert final["mission_complete"] is True

    # Debrief: honest, small, useful (§5D).
    debrief = client.get(f"/api/v1/learning-sessions/{sid}/debrief").json()
    assert debrief["xp"] > 0
    assert len(debrief["important_errors"]) <= 2
    assert debrief["pronunciation_notes"] == []  # no fake pronunciation claims
    assert ex_fail["item_id"] in debrief["failed_retrievals"]

    # Profile: recognition and production tracked separately (§34.6),
    # and the failed item is scheduled to come back (§34.7).
    profile = client.get(f"/api/v1/users/{uid}/profile").json()
    modes = {(m["item_id"], m["mode"]): m for m in profile["mastery"]}
    failed = modes[(ex_fail["item_id"], "production_prompted")]
    assert failed["strength"] == 0.0 and failed["next_review"] is not None
    assert profile["total_xp"] == debrief["xp"] or profile["total_xp"] >= debrief["xp"]

    # A second session now ambushes the weak item in Phase A.
    session2 = client.post("/api/v1/learning-sessions", json={"user_id": uid}).json()
    ambush_items = [e["item_id"] for e in session2["plan"]["phase_a"]]
    assert ex_fail["item_id"] in ambush_items
