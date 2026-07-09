"""Bakeoff manifest: speakers × conditions × content (spec §9.1–9.3).

JSON shape:
{
  "manifest_version": "1",
  "utterances": [
    {
      "id": "u001",
      "reference": "Môj prastarý otec sa narodil v Píle, pri Modre.",
      "audio_path": "audio/u001.wav",          // optional until recorded
      "speaker": {"type": "native|learner", "gender": "...", "age_band": "...", "accent": "..."},
      "condition": "quiet|street|vehicle|cheap_earbuds|airpods|phone_mic|fast|slow|hesitation",
      "proper_nouns": ["Píla", "Modra"],
      "tags": ["genealogy", "minimal_contrast", ...]
    }
  ]
}
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Utterance:
    id: str
    reference: str
    audio_path: str | None = None
    speaker: dict = field(default_factory=dict)
    condition: str = "quiet"
    proper_nouns: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    version: str
    utterances: tuple[Utterance, ...]


def load_manifest(path: str | Path) -> Manifest:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    utterances = tuple(
        Utterance(
            id=u["id"],
            reference=u["reference"],
            audio_path=u.get("audio_path"),
            speaker=u.get("speaker", {}),
            condition=u.get("condition", "quiet"),
            proper_nouns=tuple(u.get("proper_nouns", [])),
            tags=tuple(u.get("tags", [])),
        )
        for u in raw["utterances"]
    )
    return Manifest(version=raw.get("manifest_version", "1"), utterances=utterances)
