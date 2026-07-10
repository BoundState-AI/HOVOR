"""Semantic answer evaluation (spec §19) and error classification (spec §12).

Deterministic rule-based evaluator for the vertical slice. It sits behind a
stable result shape so an LLM-assisted evaluator can replace it later and
historical attempts can be rescored (attempts store scoring_version).

Never relies on literal-string equality for open production (spec §18):
normalization + acceptable variants + token-group matching.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from hovor.content.loader import Lexeme

# §12 taxonomy
CATEGORY_COMMUNICATION_BLOCKING = "communication_blocking"
CATEGORY_MEANING_CHANGED = "meaning_changed"
CATEGORY_GRAMMAR_TARGET = "grammar_target"
CATEGORY_RECURRING = "recurring_pattern"
CATEGORY_LEXICAL = "lexical_retrieval"
CATEGORY_MINOR = "minor_nonblocking"
CATEGORY_UNCERTAIN = "uncertain"


@dataclass
class ErrorTag:
    tag: str
    category: str
    detail: str = ""


@dataclass
class EvaluationResult:
    semantic_success: bool
    target_structure_success: bool | None = None
    errors: list[ErrorTag] = field(default_factory=list)
    normalized_response: str = ""
    notes: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Keeps diacritics —
    diacritic sensitivity is an explicit, separate check."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\sáäčďéíĺľňóôŕšťúýž]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _variants_for_production(lexeme: Lexeme) -> list[str]:
    return [normalize(v) for v in (lexeme.slovak, *lexeme.slovak_variants)]


def _variants_for_meaning(lexeme: Lexeme) -> list[str]:
    return [normalize(v) for v in (lexeme.english, *lexeme.english_variants)]


def evaluate_production(response: str, lexeme: Lexeme) -> EvaluationResult:
    """Learner was asked to produce the Slovak form (typed or transcribed)."""
    norm = normalize(response)
    variants = _variants_for_production(lexeme)
    result = EvaluationResult(semantic_success=False, normalized_response=norm)

    if norm in variants:
        result.semantic_success = True
        result.target_structure_success = True
        return result

    # Correct except for diacritics → communicated, but flag the minor error.
    if strip_diacritics(norm) in [strip_diacritics(v) for v in variants]:
        result.semantic_success = True
        result.target_structure_success = True
        result.errors.append(
            ErrorTag(
                tag=f"diacritic_error:{lexeme.id}",
                category=CATEGORY_MINOR,
                detail=f"Wrote '{response}' for '{lexeme.slovak}' — diacritics missing/wrong.",
            )
        )
        return result

    # Right words, wrong order → communicated, but the structure target is
    # missed (English speakers scramble clitic position, spec §12).
    bare_tokens = sorted(strip_diacritics(norm).split())
    for v in variants:
        if len(v.split()) > 1 and bare_tokens == sorted(strip_diacritics(v).split()):
            result.semantic_success = True
            result.target_structure_success = False
            result.errors.append(
                ErrorTag(
                    tag=f"word_order:{lexeme.id}",
                    category=CATEGORY_GRAMMAR_TARGET,
                    detail=f"Said '{response}' — right words, expected order '{lexeme.slovak}'.",
                )
            )
            return result

    # Shared stem, wrong ending → likely morphology, not lexical failure.
    for v in variants:
        stem = v[: max(3, len(v) - 3)]
        if len(norm) >= 3 and (norm.startswith(stem) or strip_diacritics(norm).startswith(strip_diacritics(stem))):
            result.errors.append(
                ErrorTag(
                    tag=f"ending_error:{lexeme.id}",
                    category=CATEGORY_GRAMMAR_TARGET,
                    detail=f"Got '{response}', expected '{lexeme.slovak}' — the ending changed or disappeared.",
                )
            )
            return result

    result.errors.append(
        ErrorTag(
            tag=f"retrieval_failure:{lexeme.id}",
            category=CATEGORY_LEXICAL,
            detail=f"Could not produce '{lexeme.slovak}'.",
        )
    )
    return result


def evaluate_recognition(response: str, lexeme: Lexeme) -> EvaluationResult:
    """Learner was shown/heard Slovak and asked for the meaning in English."""
    norm = normalize(response)
    result = EvaluationResult(semantic_success=False, normalized_response=norm)
    meanings = _variants_for_meaning(lexeme)
    if norm in meanings or any(m in norm for m in meanings if len(m) > 2):
        result.semantic_success = True
        return result
    result.errors.append(
        ErrorTag(
            tag=f"recognition_failure:{lexeme.id}",
            category=CATEGORY_LEXICAL,
            detail=f"Did not recognize '{lexeme.slovak}'.",
        )
    )
    return result


def evaluate_repair(response: str, repair_item: dict[str, Any]) -> EvaluationResult:
    """error_repair exercise (spec §18): the learner produces the corrected
    sentence. Diacritic slips remain minor; anything else fails with the
    item's own explanation as the detail."""
    norm = normalize(response)
    fixed = [normalize(v) for v in repair_item["fixed"]]
    result = EvaluationResult(semantic_success=False, normalized_response=norm)

    if norm in fixed:
        result.semantic_success = True
        result.target_structure_success = True
        return result
    if strip_diacritics(norm) in [strip_diacritics(v) for v in fixed]:
        result.semantic_success = True
        result.target_structure_success = True
        result.errors.append(
            ErrorTag(
                tag=f"diacritic_error:{repair_item['id']}",
                category=CATEGORY_MINOR,
                detail="Corrected sentence right, diacritics off.",
            )
        )
        return result

    result.errors.append(
        ErrorTag(
            tag=f"repair_failure:{repair_item['id']}",
            category=CATEGORY_GRAMMAR_TARGET,
            detail=repair_item.get("explanation", ""),
        )
    )
    return result


def evaluate_contrast(response: str, target: Lexeme, partner: Lexeme) -> EvaluationResult:
    """minimal_contrast exercise: distinguish two similar forms. Answering
    with the partner's meaning is a confusion-pair error — logged so the
    scheduler can keep drilling the pair (spec §2.2 confusion pairs)."""
    result = evaluate_recognition(response, target)
    if result.semantic_success:
        return result
    partner_result = evaluate_recognition(response, partner)
    if partner_result.semantic_success:
        result.errors = [
            ErrorTag(
                tag=f"confusion:{target.id}:{partner.id}",
                category=CATEGORY_LEXICAL,
                detail=f"Read '{target.slovak}' as '{partner.slovak}'.",
            )
        ]
    return result


def known_error_tags(response: str, repair_items: dict[str, dict[str, Any]], skip_item: str | None = None) -> list[ErrorTag]:
    """Match the response against the library of known learner mistakes
    (repair_items encode them, natively reviewable). A hit means we can say
    exactly WHY it's wrong, not just that it is (spec §12)."""
    bare = strip_diacritics(normalize(response))
    tags: list[ErrorTag] = []
    for item in repair_items.values():
        if item["id"] == skip_item:
            continue
        if bare == strip_diacritics(normalize(item["broken"])):
            tags.append(
                ErrorTag(
                    tag=f"known_error:{item['id']}",
                    category=CATEGORY_GRAMMAR_TARGET,
                    detail=item.get("explanation", ""),
                )
            )
    return tags


def word_disagreement(a: str, b: str) -> float:
    """Word-level edit-distance ratio between two transcripts, 0.0 (identical)
    to 1.0 (nothing shared). Used for the independent-ASR agreement check
    (spec §8.2): above threshold we refuse to score rather than guess."""
    wa, wb = normalize(a).split(), normalize(b).split()
    if not wa and not wb:
        return 0.0
    prev = list(range(len(wb) + 1))
    for i, word_a in enumerate(wa, 1):
        curr = [i]
        for j, word_b in enumerate(wb, 1):
            cost = 0 if word_a == word_b else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1] / max(len(wa), len(wb))


def match_objective(response: str, match_spec: dict[str, Any]) -> bool:
    """Objective matching for missions (spec §5 Phase C, §19): the learner
    succeeds by communicating, not by reciting one canonical sentence.

    match_spec supports:
      any_phrases: success if ANY phrase appears (diacritic-insensitive)
      all_groups:  success if EVERY group has at least one phrase present
      year_regex:  success if the regex matches (alternative to any_phrases)
    """
    norm = normalize(response)
    bare = strip_diacritics(norm)

    def present(phrase: str) -> bool:
        p = strip_diacritics(normalize(phrase))
        return p in bare

    if match_spec.get("year_regex") and re.search(match_spec["year_regex"], norm):
        return True
    if match_spec.get("any_phrases") and any(present(p) for p in match_spec["any_phrases"]):
        return True
    if match_spec.get("all_groups"):
        return all(any(present(p) for p in group) for group in match_spec["all_groups"])
    return False
