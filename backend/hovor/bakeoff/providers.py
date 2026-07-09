"""ASR providers for the bakeoff (spec §8.2, §9).

Each provider transcribes one utterance and reports latency. Real adapters
are skeletons that fail loudly with setup instructions until keys exist —
never silently, never with fake numbers.
"""

import time
from typing import Protocol

from hovor.bakeoff.manifest import Utterance


class ProviderNotConfigured(Exception):
    pass


class ASRResult:
    def __init__(self, text: str, latency_ms: float, error: str | None = None):
        self.text = text
        self.latency_ms = latency_ms
        self.error = error


class ASRProvider(Protocol):
    name: str

    def transcribe(self, utterance: Utterance) -> ASRResult: ...


class MockASRProvider:
    """Deterministic fake for harness development and tests. Behavior is a
    dict of utterance-id → hypothesis; anything unlisted echoes the reference
    (a 'perfect' provider). `degrade` strips diacritics to simulate a
    diacritic-blind provider."""

    def __init__(self, name: str = "mock-asr", hypotheses: dict[str, str] | None = None,
                 degrade_diacritics: bool = False, latency_ms: float = 120.0):
        self.name = name
        self._hypotheses = hypotheses or {}
        self._degrade = degrade_diacritics
        self._latency = latency_ms

    def transcribe(self, utterance: Utterance) -> ASRResult:
        text = self._hypotheses.get(utterance.id, utterance.reference)
        if self._degrade:
            from hovor.services.evaluation import strip_diacritics

            text = strip_diacritics(text)
        return ASRResult(text=text, latency_ms=self._latency)


def _timed(fn) -> ASRResult:
    start = time.perf_counter()
    text = fn()
    return ASRResult(text=text, latency_ms=(time.perf_counter() - start) * 1000)


class OpenAIWhisperASR:
    """OpenAI transcription API (whisper / gpt-4o-transcribe family)."""

    name = "openai"

    def __init__(self, model: str = "gpt-4o-transcribe"):
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderNotConfigured("set OPENAI_API_KEY to bench OpenAI ASR")
        self._model = model

    def transcribe(self, utterance: Utterance) -> ASRResult:
        if not utterance.audio_path:
            return ASRResult("", 0.0, error="no audio recorded for this utterance yet")
        from openai import OpenAI  # lazy: not a base dependency

        client = OpenAI()
        return _timed(
            lambda: client.audio.transcriptions.create(
                model=self._model, language="sk",
                file=open(utterance.audio_path, "rb"),
            ).text
        )


class AzureASR:
    """Azure Speech, sk-SK locale (documented Slovak support)."""

    name = "azure"

    def __init__(self):
        import os

        if not (os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION")):
            raise ProviderNotConfigured(
                "set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION to bench Azure; "
                "pip install azure-cognitiveservices-speech"
            )

    def transcribe(self, utterance: Utterance) -> ASRResult:
        if not utterance.audio_path:
            return ASRResult("", 0.0, error="no audio recorded for this utterance yet")
        import os

        import azure.cognitiveservices.speech as speechsdk  # lazy

        config = speechsdk.SpeechConfig(
            subscription=os.environ["AZURE_SPEECH_KEY"], region=os.environ["AZURE_SPEECH_REGION"]
        )
        config.speech_recognition_language = "sk-SK"
        audio = speechsdk.AudioConfig(filename=utterance.audio_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio)
        return _timed(lambda: recognizer.recognize_once().text)


class GoogleASR:
    """Google Cloud Speech-to-Text, sk-SK (documented Slovak support)."""

    name = "google"

    def __init__(self):
        import os

        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ProviderNotConfigured(
                "set GOOGLE_APPLICATION_CREDENTIALS to bench Google; "
                "pip install google-cloud-speech"
            )

    def transcribe(self, utterance: Utterance) -> ASRResult:
        if not utterance.audio_path:
            return ASRResult("", 0.0, error="no audio recorded for this utterance yet")
        from google.cloud import speech  # lazy

        client = speech.SpeechClient()

        def run():
            with open(utterance.audio_path, "rb") as f:
                audio = speech.RecognitionAudio(content=f.read())
            config = speech.RecognitionConfig(language_code="sk-SK")
            response = client.recognize(config=config, audio=audio)
            return " ".join(r.alternatives[0].transcript for r in response.results)

        return _timed(run)


class ElevenLabsASR:
    """ElevenLabs STT (documented Slovak in the multilingual stack)."""

    name = "elevenlabs"

    def __init__(self):
        import os

        if not os.environ.get("ELEVENLABS_API_KEY"):
            raise ProviderNotConfigured("set ELEVENLABS_API_KEY to bench ElevenLabs")

    def transcribe(self, utterance: Utterance) -> ASRResult:
        if not utterance.audio_path:
            return ASRResult("", 0.0, error="no audio recorded for this utterance yet")
        from elevenlabs.client import ElevenLabs  # lazy

        client = ElevenLabs()
        return _timed(
            lambda: client.speech_to_text.convert(
                file=open(utterance.audio_path, "rb"), model_id="scribe_v1", language_code="sk"
            ).text
        )


REGISTRY = {
    "mock": MockASRProvider,
    "openai": OpenAIWhisperASR,
    "azure": AzureASR,
    "google": GoogleASR,
    "elevenlabs": ElevenLabsASR,
}
