"""CLI: python -m hovor.bakeoff <manifest.json> [--providers mock,azure,...]

Providers missing keys are reported and skipped — the bench never fakes a
result for a provider it can't reach.
"""

import argparse
import sys

from hovor.bakeoff.manifest import load_manifest
from hovor.bakeoff.providers import REGISTRY, ProviderNotConfigured
from hovor.bakeoff.runner import render_markdown, run_bakeoff


def main() -> int:
    parser = argparse.ArgumentParser(description="HOVOR! Slovak speech bakeoff")
    parser.add_argument("manifest")
    parser.add_argument("--providers", default="mock")
    parser.add_argument("--out", default="VOICE_BENCHMARK_REPORT_v1.md")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    providers = []
    for name in args.providers.split(","):
        name = name.strip()
        if name not in REGISTRY:
            print(f"unknown provider '{name}' (known: {', '.join(REGISTRY)})", file=sys.stderr)
            return 2
        try:
            providers.append(REGISTRY[name]())
        except ProviderNotConfigured as exc:
            print(f"skipping {name}: {exc}", file=sys.stderr)

    if not providers:
        print("no runnable providers", file=sys.stderr)
        return 1

    report = run_bakeoff(manifest, providers)
    markdown = render_markdown(report)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(markdown)
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
