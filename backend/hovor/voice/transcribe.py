"""Server-side Slovak speech-to-text for push-to-talk (spec §8, §32).

The browser records (MediaRecorder — available everywhere, including iOS
Safari where SpeechRecognition is not) and posts the clip here. Audio is
transcribed and discarded — never stored (§31; retention is a separate,
consent-gated concern).
"""

import os

import httpx

TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIBE_MODEL = "gpt-4o-transcribe"
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # push-to-talk clips are seconds, not songs


class TranscriptionUnavailable(Exception):
    """Transcription backend cannot run (missing key, upstream failure)."""


def openai_transcribe(audio: bytes, filename: str, content_type: str) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise TranscriptionUnavailable("OPENAI_API_KEY is not set — speech input needs it")
    response = httpx.post(
        TRANSCRIBE_URL,
        headers={"Authorization": f"Bearer {key}"},
        data={"model": TRANSCRIBE_MODEL, "language": "sk"},
        files={"file": (filename, audio, content_type)},
        timeout=60,
    )
    if response.status_code != 200:
        raise TranscriptionUnavailable(f"transcription upstream returned {response.status_code}")
    return response.json().get("text", "").strip()
