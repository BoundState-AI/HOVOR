"""Bakeoff runner: manifest × providers → VOICE_BENCHMARK_REPORT."""

from hovor.bakeoff.manifest import Manifest
from hovor.bakeoff.metrics import cer, diacritic_error_rate, proper_noun_accuracy, wer


def run_bakeoff(manifest: Manifest, providers: list) -> dict:
    report = {"manifest_version": manifest.version, "utterances": len(manifest.utterances),
              "providers": {}}
    for provider in providers:
        rows = []
        failures = []
        for utterance in manifest.utterances:
            result = provider.transcribe(utterance)
            if result.error:
                failures.append({"utterance_id": utterance.id, "error": result.error})
                continue
            pn = proper_noun_accuracy(result.text, list(utterance.proper_nouns))
            rows.append({
                "utterance_id": utterance.id,
                "condition": utterance.condition,
                "speaker_type": utterance.speaker.get("type", "unknown"),
                "hypothesis": result.text,
                "wer": wer(utterance.reference, result.text),
                "cer": cer(utterance.reference, result.text),
                "diacritic_error_rate": diacritic_error_rate(utterance.reference, result.text),
                "proper_noun_exact": pn["exact"],
                "proper_noun_loose": pn["loose"],
                "latency_ms": result.latency_ms,
            })
        report["providers"][provider.name] = {
            "rows": rows,
            "failures": failures,
            "summary": _summarize(rows),
            "by_condition": _breakdown(rows, "condition"),
            "by_speaker_type": _breakdown(rows, "speaker_type"),
        }
    report["ranking"] = sorted(
        (name for name, data in report["providers"].items() if data["summary"]),
        key=lambda name: report["providers"][name]["summary"]["wer_mean"],
    )
    return report


def _mean(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _summarize(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    return {
        "wer_mean": _mean([r["wer"] for r in rows]),
        "cer_mean": _mean([r["cer"] for r in rows]),
        "diacritic_error_rate_mean": _mean([r["diacritic_error_rate"] for r in rows]),
        "proper_noun_exact_mean": _mean([r["proper_noun_exact"] for r in rows]),
        "proper_noun_loose_mean": _mean([r["proper_noun_loose"] for r in rows]),
        "latency_ms_mean": _mean([r["latency_ms"] for r in rows]),
        "n": len(rows),
    }


def _breakdown(rows: list[dict], key: str) -> dict:
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r[key], []).append(r)
    return {k: _summarize(v) for k, v in sorted(groups.items())}


def render_markdown(report: dict) -> str:
    lines = [
        "# VOICE_BENCHMARK_REPORT_v1",
        "",
        f"Utterances: {report['utterances']} · Providers: {len(report['providers'])}",
        "",
        "Lower WER/CER/diacritic rate is better; higher proper-noun accuracy is better.",
        "",
        "| provider | WER | CER | diacritic err | proper noun (exact/loose) | latency ms | n |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in report["ranking"]:
        s = report["providers"][name]["summary"]
        pn = f"{s['proper_noun_exact_mean']}/{s['proper_noun_loose_mean']}"
        lines.append(
            f"| {name} | {s['wer_mean']} | {s['cer_mean']} | "
            f"{s['diacritic_error_rate_mean']} | {pn} | {s['latency_ms_mean']} | {s['n']} |"
        )
    lines.append("")
    for name, data in report["providers"].items():
        if data["failures"]:
            lines.append(f"## {name}: {len(data['failures'])} failures")
            for f in data["failures"][:10]:
                lines.append(f"- `{f['utterance_id']}`: {f['error']}")
            lines.append("")
        if data["by_condition"]:
            lines.append(f"## {name} by condition")
            lines.append("| condition | WER | diacritic err | n |")
            lines.append("|---|---|---|---|")
            for cond, s in data["by_condition"].items():
                lines.append(f"| {cond} | {s['wer_mean']} | {s['diacritic_error_rate_mean']} | {s['n']} |")
            lines.append("")
    if report["ranking"]:
        lines.append(f"**Winner by mean WER: `{report['ranking'][0]}`** — but read the "
                     "per-condition and learner-accent breakdowns before believing it.")
    return "\n".join(lines)
