"""Bakeoff metrics (spec §9.4).

All text is normalized (lowercased, punctuation stripped) before measuring;
diacritics are preserved because Slovak diacritic fidelity is itself a metric.
"""

from hovor.services.evaluation import normalize, strip_diacritics


def _edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, item_a in enumerate(a, 1):
        curr = [i]
        for j, item_b in enumerate(b, 1):
            cost = 0 if item_a == item_b else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: word-level edit distance over reference length."""
    ref = normalize(reference).split()
    hyp = normalize(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate (diacritics count — ď ≠ d)."""
    ref = list(normalize(reference))
    hyp = list(normalize(hypothesis))
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def diacritic_error_rate(reference: str, hypothesis: str) -> float:
    """The share of character errors attributable to diacritics alone:
    CER with diacritics minus CER after stripping them. A provider that hears
    'pat' for 'päť' scores badly here even though the letters are 'close'."""
    full = cer(reference, hypothesis)
    stripped = cer(strip_diacritics(normalize(reference)), strip_diacritics(normalize(hypothesis)))
    return max(0.0, full - stripped)


def _stems(noun: str) -> list[str]:
    """Slovak declines proper nouns (Modra → v Modre, Pezinok → do Pezinka),
    so match on stems: each word minus up to two trailing letters."""
    return [w[: max(3, len(w) - 2)] for w in normalize(noun).split()]


def proper_noun_accuracy(hypothesis: str, proper_nouns: list[str]) -> dict:
    """How many of the utterance's proper nouns survived transcription —
    exact (diacritics required) and loose (diacritics forgiven), inflection
    tolerated in both. Generic systems break on Svätý Jur; this catches it
    (spec §9.3)."""
    if not proper_nouns:
        return {"exact": None, "loose": None}
    hyp = normalize(hypothesis)
    hyp_bare = strip_diacritics(hyp)
    exact = sum(1 for p in proper_nouns if all(s in hyp for s in _stems(p)))
    loose = sum(
        1 for p in proper_nouns if all(strip_diacritics(s) in hyp_bare for s in _stems(p))
    )
    return {"exact": exact / len(proper_nouns), "loose": loose / len(proper_nouns)}
