"""Batch recall (spec §13): after a batch of new words, each one is tested
again at a distance — the immediate say-it-back echo is not retrieval."""

from hovor.models.learner import User
from hovor.services.session_composer import compose_session


def _user(db) -> int:
    user = User(name="Recall")
    db.add(user)
    db.flush()
    return user.id


def test_new_material_batch_gets_a_recall_round(db, content):
    session = compose_session(db, _user(db), content)
    introduced = [e["introduce"]["item_id"] for e in session.plan["phase_b"]]
    recalled = [ex["item_id"] for ex in session.plan["phase_b_recall"]]
    assert len(introduced) >= 3
    assert recalled == introduced  # same words, introduction order = max gap
    for ex in session.plan["phase_b_recall"]:
        assert ex["mode"] == "production_prompted"


def test_recall_round_exercises_are_scoreable(client):
    uid = client.post("/api/v1/users", json={"name": "RecallFlow"}).json()["id"]
    session = client.post("/api/v1/learning-sessions", json={"user_id": uid}).json()
    recall = session["plan"]["phase_b_recall"]
    assert recall, "fresh user with a full new-material batch must get recall"
    ex = recall[0]
    out = client.post(
        "/api/v1/attempts",
        json={
            "user_id": uid,
            "session_id": session["session_id"],
            "exercise_id": ex["exercise_id"],
            "response": "definitely wrong answer",
        },
    ).json()
    assert out["semantic_success"] is False
    assert out["expected"]  # the corrected form comes back
