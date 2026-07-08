"""Build 0 bakeoff harness: metrics, runner, report (spec §9, §33)."""

from pathlib import Path

from hovor.bakeoff.manifest import load_manifest
from hovor.bakeoff.metrics import cer, diacritic_error_rate, proper_noun_accuracy, wer
from hovor.bakeoff.providers import MockASRProvider
from hovor.bakeoff.runner import render_markdown, run_bakeoff

SAMPLE = Path(__file__).parent.parent / "hovor" / "bakeoff" / "sample_manifest.json"


def test_wer_basics():
    assert wer("kde je stanica", "kde je stanica") == 0.0
    assert wer("kde je stanica", "kde je") == 1 / 3          # one deletion
    assert wer("kde je stanica", "kedy je stanica") == 1 / 3  # one substitution


def test_cer_counts_diacritics():
    assert cer("päť", "pat") > 0.0
    assert cer("päť", "päť") == 0.0


def test_diacritic_error_rate_isolates_diacritics():
    # Only diacritics wrong → full CER is all diacritic error.
    rate = diacritic_error_rate("päť šesť", "pat sest")
    assert rate > 0.3
    # Genuinely different words → error is NOT attributed to diacritics.
    assert diacritic_error_rate("vlak", "autobus") == 0.0
    assert diacritic_error_rate("päť", "päť") == 0.0


def test_proper_noun_accuracy_exact_vs_loose():
    # Diacritics stripped by a bad provider: exact fails, loose forgives —
    # and declined forms (v... Jure, pri Bratislave) still count via stems.
    pn = proper_noun_accuracy("byvame vo svatom jure pri bratislave", ["Svätý Jur", "Bratislava"])
    assert pn["exact"] == 0.5   # 'bratislav' has no diacritics to lose; 'svät' does
    assert pn["loose"] == 1.0
    # Correct diacritics, declined: full marks.
    pn2 = proper_noun_accuracy("hľadám záznam v Modre a v Píle", ["Modra", "Píla"])
    assert pn2["exact"] == 1.0
    # Wrong place entirely: zero.
    pn3 = proper_noun_accuracy("hľadám záznam v Košiciach", ["Modra"])
    assert pn3["exact"] == 0.0 and pn3["loose"] == 0.0


def test_runner_ranks_providers_and_renders_report():
    manifest = load_manifest(SAMPLE)
    perfect = MockASRProvider(name="perfect")
    diacritic_blind = MockASRProvider(name="diacritic-blind", degrade_diacritics=True, latency_ms=300)
    sloppy = MockASRProvider(
        name="sloppy",
        hypotheses={u.id: "no rozumiem vam vobec" for u in manifest.utterances},
    )
    report = run_bakeoff(manifest, [sloppy, perfect, diacritic_blind])

    assert report["ranking"][0] == "perfect"
    assert report["ranking"][-1] == "sloppy"
    assert report["providers"]["perfect"]["summary"]["wer_mean"] == 0.0
    blind = report["providers"]["diacritic-blind"]["summary"]
    assert blind["diacritic_error_rate_mean"] > 0.0
    assert blind["proper_noun_exact_mean"] < blind["proper_noun_loose_mean"]

    markdown = render_markdown(report)
    assert "VOICE_BENCHMARK_REPORT_v1" in markdown
    assert "| perfect |" in markdown and "| sloppy |" in markdown
    assert "by condition" in markdown


def test_missing_audio_is_a_failure_not_a_fake_result():
    """Real providers must never fabricate numbers for unrecorded utterances."""
    manifest = load_manifest(SAMPLE)

    class NoAudioProvider:
        name = "strict"

        def transcribe(self, utterance):
            from hovor.bakeoff.providers import ASRResult

            if not utterance.audio_path:
                return ASRResult("", 0.0, error="no audio recorded for this utterance yet")
            return ASRResult(utterance.reference, 1.0)

    report = run_bakeoff(manifest, [NoAudioProvider()])
    data = report["providers"]["strict"]
    assert len(data["failures"]) == len(manifest.utterances)
    assert data["summary"] is None  # no fabricated summary
    assert "strict" not in report["ranking"]
