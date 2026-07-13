"""On-demand pronunciation audio (spec §18 listening modes, §2.3-safe).

Models pronunciation — never grades it. Synthesis is restricted to strings
that exist in the versioned content bundle, which bounds the endpoint to a
finite, cacheable set: no free-text abuse surface, and every word is paid
for at most once per process (plus edge/browser caching upstream).
"""

import os
from typing import Callable

import httpx

TTS_URL = "https://api.openai.com/v1/audio/speech"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "coral"
TTS_INSTRUCTIONS = (
    "You are a native Slovak speaker recording pronunciation examples for "
    "language learners. Pronounce the text clearly and naturally, at a "
    "slightly unhurried pace, with correct Slovak diacritics and stress."
)
MAX_TEXT_LEN = 200

Synthesizer = Callable[[str], bytes]

_audio_cache: dict[str, bytes] = {}
_speakable_cache: dict[str, set[str]] = {}


class TTSUnavailable(Exception):
    """Synthesis backend cannot run (missing key, upstream failure)."""


def speakable_strings(content) -> set[str]:
    """Every Slovak string a client may legitimately ask to hear, exactly as
    the content bundle ships it (exact-match contract with the client)."""
    cached = _speakable_cache.get(content.content_version)
    if cached is not None:
        return cached

    out: set[str] = set()
    for lexeme in content.lexemes.values():
        out.add(lexeme.slovak)
        out.update(lexeme.slovak_variants)
    for mission in content.missions.values():
        for line_key in ("opening_line", "completion_line"):
            line = mission.get(line_key)
            if isinstance(line, dict) and line.get("slovak"):
                out.add(line["slovak"])
        for objective in mission.get("objectives", []):
            for part in ("elicit", "ack"):
                block = objective.get(part) or {}
                if block.get("slovak"):
                    out.add(block["slovak"])
            for hint in objective.get("hints", []):
                if hint.get("text"):
                    out.add(hint["text"])
    for item in content.repair_items.values():
        out.add(item["broken"])
        out.update(item["fixed"])
    # Day-0 alphabet primer (spec §18 hear-it applies to every content string):
    # letters, example words, contrast words, and typing-practice words.
    alphabet = content.alphabet or {}
    for letter in alphabet.get("letters", []):
        if letter.get("char"):
            out.add(letter["char"])
        for example in letter.get("examples", []):
            if example.get("slovak"):
                out.add(example["slovak"])
    for pair in alphabet.get("contrast_pairs", []):
        for key in ("a", "b", "word_a", "word_b"):
            if pair.get(key):
                out.add(pair[key])
    out.update(alphabet.get("practice_words", []))

    _speakable_cache[content.content_version] = out
    return out


def openai_synthesize(text: str) -> bytes:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise TTSUnavailable("OPENAI_API_KEY is not set — pronunciation audio needs it")
    response = httpx.post(
        TTS_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": TTS_MODEL,
            "voice": TTS_VOICE,
            "input": text,
            "instructions": TTS_INSTRUCTIONS,
            "response_format": "mp3",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise TTSUnavailable(f"TTS upstream returned {response.status_code}")
    return response.content


def synthesize_cached(text: str, synthesizer: Synthesizer) -> bytes:
    cache_key = f"{TTS_VOICE}:{text}"
    audio = _audio_cache.get(cache_key)
    if audio is None:
        audio = synthesizer(text)
        _audio_cache[cache_key] = audio
    return audio
