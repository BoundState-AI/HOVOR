"""Day-0 alphabet primer: complete letter set, speakable strings, optional
content file, and campaign/mission fixes shipped in ancestry-slice-0.2.3."""

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from hovor.content.loader import load_content
from hovor.core.config import settings
from hovor.core.db import get_db
from hovor.main import create_app
from hovor.api.routes import get_synthesizer
from hovor.services.evaluation import match_objective
from hovor.voice.tts import _audio_cache, speakable_strings

FAKE_MP3 = b"ID3fake-mp3-bytes"


def _client(db, synth=None):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: iter([db])
    if synth is not None:
        app.dependency_overrides[get_synthesizer] = lambda: synth
    return TestClient(app)


def test_alphabet_endpoint_serves_the_full_46_letter_alphabet(db):
    r = _client(db).get("/api/v1/alphabet")
    assert r.status_code == 200
    data = r.json()
    chars = [l["char"] for l in data["letters"]]
    assert len(chars) == 46
    for digraph in ("ch", "dz", "dž"):
        assert digraph in chars
    # Every letter carries a real example word, not a bare letter.
    for letter in data["letters"]:
        example = letter["examples"][0]["slovak"]
        assert example and example != letter["char"]
    assert data["practice_words"], "practice words belong to the versioned bundle"


def test_contrast_pairs_are_labeled_consistently(content):
    for pair in content.alphabet["contrast_pairs"]:
        # The words must actually demonstrate the letters the pair claims.
        assert pair["a"] in pair["word_a"], pair["id"]
        assert pair["b"] in pair["word_b"], pair["id"]
        assert pair["gloss_a"] and pair["gloss_b"]


def test_every_primer_string_is_speakable(content):
    speakable = speakable_strings(content)
    alphabet = content.alphabet
    for letter in alphabet["letters"]:
        assert letter["char"] in speakable
        assert letter["examples"][0]["slovak"] in speakable
    for pair in alphabet["contrast_pairs"]:
        assert pair["word_a"] in speakable and pair["word_b"] in speakable
    for word in alphabet["practice_words"]:
        assert word in speakable


def test_tts_serves_a_bare_letter(db):
    _audio_cache.clear()
    calls = []

    def fake_synth(text: str) -> bytes:
        calls.append(text)
        return FAKE_MP3

    r = _client(db, fake_synth).get("/api/v1/tts", params={"text": "á"})
    assert r.status_code == 200
    assert calls == ["á"]


def test_loader_tolerates_missing_alphabet_json(tmp_path):
    src = settings.content_dir
    for f in src.glob("*.json"):
        if f.name != "alphabet.json":
            shutil.copy(f, tmp_path / f.name)
    bundle = load_content.__wrapped__(str(tmp_path))
    assert bundle.alphabet == {}
    assert speakable_strings(bundle)  # lexemes still speakable, no crash


def test_modra_unlock_is_not_gated_on_pezinok(content):
    modra = next(r for r in content.campaign["regions"] if r["id"] == "modra")
    assert modra["unlock"]["missions"] == ["svaty_jur_family"], (
        "gating Modra behind the new Pezinok mission retroactively re-locks "
        "a region existing learners already had open"
    )


def test_repair_direction_accepts_the_natural_correction(content):
    mission = content.mission("pezinok_square_stop")
    objective = next(o for o in mission["objectives"] if o["id"] == "repair_direction")
    assert match_objective("Nie, do Modry!", objective["match"])
    assert match_objective("Nie, idem do Modry.", objective["match"])


def test_pezinok_ack_uses_correct_numeral_gender(content):
    mission = content.mission("pezinok_square_stop")
    blob = json.dumps(mission, ensure_ascii=False)
    assert "Dva eurá" not in blob and "Dve eurá" in blob
