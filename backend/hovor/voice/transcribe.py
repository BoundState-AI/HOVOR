"""Server-side Slovak speech-to-text for push-to-talk (spec §8, §32).

The browser records (MediaRecorder — available everywhere, including iOS
Safari where SpeechRecognition is not) and posts the clip here. Audio is
transcribed and discarded — never stored (§31; retention is a separate,
consent-gated concern).

Script drift: Slovak learner speech is acoustically close to Russian
("dobrý deň" ≈ "добрый день"), and the ASR sometimes answers in Cyrillic
even with language=sk. Defense in depth: a Slovak Latin-script prompt, one
retry on Cyrillic output, then transliteration as the last resort — the
learner must never see their own Slovak echoed back in Cyrillic.
"""

import os

import httpx

TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIBE_MODEL = "gpt-4o-transcribe"
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # push-to-talk clips are seconds, not songs

# Few-shot style guide for the ASR: Slovak, Latin script, real diacritics.
SLOVAK_PROMPT = (
    "Slovenčina, latinka so slovenskou diakritikou (nikdy azbuka). "
    "Dobrý deň. Ahoj. Prosím si lístok do Pezinka. Ďakujem pekne. "
    "Volám sa Ján. Jednosmerný alebo spiatočný?"
)
RETRY_PROMPT = (
    "The audio is SLOVAK. Transcribe in the LATIN alphabet with Slovak "
    "diacritics (á ä č ď é í ľ ň ó ô ŕ š ť ú ý ž). Never use Cyrillic. " + SLOVAK_PROMPT
)

# Last-resort Cyrillic → Slovak-Latin mapping (readability rescue, not
# orthography): keeps the learner's echo legible if the retry also drifts.
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "jo",
    "ж": "ž", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "ch", "ц": "c", "ч": "č", "ш": "š", "щ": "šč", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "ju", "я": "ja", "і": "i", "ї": "ji",
    "є": "je", "ґ": "g",
}


class TranscriptionUnavailable(Exception):
    """Transcription backend cannot run (missing key, upstream failure)."""


def contains_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


def latinize(text: str) -> str:
    out = []
    for ch in text:
        low = ch.lower()
        if low in _CYR:
            mapped = _CYR[low]
            out.append(mapped.capitalize() if ch.isupper() and mapped else mapped)
        else:
            out.append(ch)
    return "".join(out)


def ensure_latin(text: str) -> str:
    return latinize(text) if contains_cyrillic(text) else text


def _call(key: str, audio: bytes, filename: str, content_type: str, prompt: str) -> str:
    response = httpx.post(
        TRANSCRIBE_URL,
        headers={"Authorization": f"Bearer {key}"},
        data={"model": TRANSCRIBE_MODEL, "language": "sk", "prompt": prompt},
        files={"file": (filename, audio, content_type)},
        timeout=60,
    )
    if response.status_code != 200:
        raise TranscriptionUnavailable(f"transcription upstream returned {response.status_code}")
    return response.json().get("text", "").strip()


def openai_transcribe(audio: bytes, filename: str, content_type: str) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise TranscriptionUnavailable("OPENAI_API_KEY is not set — speech input needs it")
    text = _call(key, audio, filename, content_type, SLOVAK_PROMPT)
    if contains_cyrillic(text):
        text = _call(key, audio, filename, content_type, RETRY_PROMPT)
    return ensure_latin(text)
