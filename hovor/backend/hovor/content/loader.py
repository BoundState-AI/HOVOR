"""Versioned content loading (spec §20, §34.14).

Content lives in versioned JSON files, not in code and not in the learner
database. The DB stores learner state that references content by id +
content_version, so content can be revised and attempts re-scored later.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from hovor.core.config import settings


@dataclass(frozen=True)
class Lexeme:
    id: str
    slovak: str
    english: str
    english_variants: tuple[str, ...]
    slovak_variants: tuple[str, ...]
    pos: str
    register: str
    skill_nodes: tuple[str, ...]
    proper_noun: bool


@dataclass(frozen=True)
class SkillNode:
    id: str
    kind: str
    title: str
    stage: int


@dataclass(frozen=True)
class ContentBundle:
    content_version: str
    review_status: str
    lexemes: dict[str, Lexeme]
    skill_nodes: dict[str, SkillNode]
    skill_edges: tuple[tuple[str, str], ...]
    missions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def lexeme(self, lexeme_id: str) -> Lexeme:
        return self.lexemes[lexeme_id]

    def mission(self, mission_id: str) -> dict[str, Any]:
        return self.missions[mission_id]


def _read(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_content(content_dir: str | None = None) -> ContentBundle:
    base = Path(content_dir) if content_dir else settings.content_dir
    lex_raw = _read(base / "lexemes.json")
    skills_raw = _read(base / "skills.json")
    missions_raw = _read(base / "missions.json")

    lexemes = {
        item["id"]: Lexeme(
            id=item["id"],
            slovak=item["slovak"],
            english=item["english"],
            english_variants=tuple(item.get("english_variants", [])),
            slovak_variants=tuple(item.get("slovak_variants", [])),
            pos=item["pos"],
            register=item["register"],
            skill_nodes=tuple(item.get("skill_nodes", [])),
            proper_noun=item.get("proper_noun", False),
        )
        for item in lex_raw["lexemes"]
    }
    skill_nodes = {
        n["id"]: SkillNode(id=n["id"], kind=n["kind"], title=n["title"], stage=n["stage"])
        for n in skills_raw["nodes"]
    }
    edges = tuple((e["from"], e["to"]) for e in skills_raw["edges"])
    missions = {m["id"]: m for m in missions_raw["missions"]}

    return ContentBundle(
        content_version=lex_raw["content_version"],
        review_status=lex_raw.get("review_status", "UNKNOWN"),
        lexemes=lexemes,
        skill_nodes=skill_nodes,
        skill_edges=edges,
        missions=missions,
    )
