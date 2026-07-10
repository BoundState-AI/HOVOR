"""Cyrillic drift guard (ASR answering Slovak in Russian script) and the
corrected-form feedback after a miss (spec §12 — never a raw error tag)."""

from fastapi.testclient import TestClient

from hovor.core.db import get_db
from hovor.main import create_app
from hovor.api.routes import get_transcriber
from hovor.services.attempts import submit_exercise_attempt
from hovor.voice.transcribe import contains_cyrillic, ensure_latin, latinize


def test_cyrillic_detection_and_transliteration():
    assert contains_cyrillic("Добрый день")
    assert not contains_cyrillic("Dobrý deň, prosím?")
    assert latinize("Добрый день") == "Dobryj den"
    assert ensure_latin("Ахой") == "Achoj"
    assert ensure_latin("Dobrý deň") == "Dobrý deň"  # untouched


def test_transcribe_route_latinizes_any_backend_output(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: iter([db])
    app.dependency_overrides[get_transcriber] = lambda: (lambda *a: "Добрый день")
    client = TestClient(app)
    r = client.post(
        "/api/v1/transcribe",
        files={"audio": ("s.webm", b"bytes", "audio/webm")},
    )
    assert r.status_code == 200
    assert r.json()["text"] == "Dobryj den"  # Latin, whatever the ASR did


def _make_user(db):
    from hovor.models.learner import User

    user = User(name="Feedback")
    db.add(user)
    db.flush()
    return user.id


def test_missed_production_shows_the_slovak_answer(db, content):
    uid = _make_user(db)
    attempt, extras = submit_exercise_attempt(
        db, uid, None, "dobry_den:production_prompted", "Добрый день", content
    )
    assert attempt.semantic_success is False
    assert extras["expected"] == "dobrý deň"
    assert extras["expected_speakable"] is True


def test_missed_recognition_shows_the_english_gloss(db, content):
    uid = _make_user(db)
    attempt, extras = submit_exercise_attempt(
        db, uid, None, "dobry_den:recognition_text", "totally wrong", content
    )
    assert attempt.semantic_success is False
    assert extras["expected"]  # the gloss
    assert extras["expected_speakable"] is False


def test_correct_answer_reveals_nothing(db, content):
    uid = _make_user(db)
    attempt, extras = submit_exercise_attempt(
        db, uid, None, "ahoj:production_prompted", "ahoj", content
    )
    assert attempt.semantic_success is True
    assert "expected" not in extras
