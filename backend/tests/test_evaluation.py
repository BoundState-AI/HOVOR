"""Spec §18/§19: no literal-string equality; multiple valid phrasings;
error taxonomy of §12."""

from hovor.services.evaluation import (
    evaluate_production,
    evaluate_recognition,
    match_objective,
)


def test_exact_production(content):
    result = evaluate_production("ďakujem", content.lexeme("dakujem"))
    assert result.semantic_success and not result.errors


def test_diacritic_slip_communicates_but_is_flagged(content):
    result = evaluate_production("dakujem", content.lexeme("dakujem"))
    assert result.semantic_success  # they communicated
    assert any(e.tag.startswith("diacritic_error") for e in result.errors)
    assert result.errors[0].category == "minor_nonblocking"


def test_wrong_ending_is_grammar_not_lexical(content):
    result = evaluate_production("rozumiete", content.lexeme("rozumiem"))
    assert not result.semantic_success
    assert result.errors[0].category == "grammar_target"


def test_total_retrieval_failure(content):
    result = evaluate_production("pes", content.lexeme("vlak"))
    assert not result.semantic_success
    assert result.errors[0].category == "lexical_retrieval"


def test_recognition_accepts_variants(content):
    assert evaluate_recognition("train", content.lexeme("vlak")).semantic_success
    assert evaluate_recognition("a train", content.lexeme("vlak")).semantic_success
    assert not evaluate_recognition("bus", content.lexeme("vlak")).semantic_success


def test_slovak_variant_accepted(content):
    # "do videnia" is an accepted variant of "dovidenia"
    assert evaluate_production("do videnia", content.lexeme("dovidenia")).semantic_success


def test_objective_matching_multiple_phrasings(content):
    mission = content.mission("modra_archive_records")
    explain = next(o for o in mission["objectives"] if o["id"] == "explain_ancestor")
    # Three different valid ways to communicate the same thing:
    assert match_objective("Môj prastarý otec sa narodil v Píle.", explain["match"])
    assert match_objective("prastary otec sa narodil pri modre", explain["match"])
    assert match_objective("Môj pradedko... narodil sa v dedine Píla", explain["match"])
    # Missing the past-tense structure → not satisfied:
    assert not match_objective("prastarý otec Píla", explain["match"])


def test_year_answer_matches(content):
    mission = content.mission("modra_archive_records")
    year_q = next(o for o in mission["objectives"] if o["id"] == "understand_question")
    assert match_objective("Narodil sa v roku 1898.", year_q["match"])
    assert match_objective("neviem", year_q["match"])
    assert not match_objective("v Píle", year_q["match"])
