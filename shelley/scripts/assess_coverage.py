#!/usr/bin/env python3
"""
Report field-coverage statistics for shelley metadata sources.

Usage:
    python3 shelley/scripts/assess_coverage.py [rsec|toolfinder]

Without an argument, both sources are reported.
Reads the committed artifacts — no network access required.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RSEC_FILE = DATA_DIR / "rsec_meta.json.gz"
TF_FILE = DATA_DIR / "toolfinder_meta.yaml"

TF_FIELDS = [
    "id",
    "name",
    "description",
    "biotools",
    "biocontainers",
    "edam-operations",
    "edam-topics",
    "edam-inputs",
    "edam-outputs",
    "homepage",
    "license",
]

RSEC_FIELDS = [
    "name",
    "description",
    "homepage",
    "license",
    "edam-operations",
    "edam-topics",
    "edam-inputs",
    "edam-outputs",
]


def _bar(pct: float) -> str:
    return "#" * int(pct / 5)


def report_toolfinder() -> None:
    if not TF_FILE.exists():
        print(f"[toolfinder] File not found: {TF_FILE}", file=sys.stderr)
        return
    with open(TF_FILE) as f:
        entries = yaml.safe_load(f)
    total = len(entries)
    print(f"[toolfinder]  {TF_FILE}")
    print(f"  Entries: {total}\n")
    print(f"  {'Field':<22} {'Coverage':>9}")
    print("  " + "-" * 34)
    for field in TF_FIELDS:
        pct = 100.0 * sum(1 for e in entries if e.get(field)) / total
        print(f"  {field:<22} {pct:>8.1f}%  {_bar(pct)}")


def report_rsec() -> None:
    if not RSEC_FILE.exists():
        print(f"[rsec] File not found: {RSEC_FILE}", file=sys.stderr)
        print("[rsec] Run: shelley-build-rsec", file=sys.stderr)
        return
    with gzip.open(RSEC_FILE, "rt") as f:
        doc = json.load(f)
    print(f"[rsec]  {RSEC_FILE}")
    print(f"  Source commit : {doc.get('source_commit', 'unknown')}")
    print(f"  Generated at  : {doc.get('generated_at', 'unknown')}")
    print(f"  Entries       : {doc['entry_count']}\n")
    coverage = doc.get("field_coverage", {})
    if not coverage:
        # Recompute from entries if artifact predates field_coverage embedding
        entries = doc["entries"]
        total = len(entries)
        coverage = {
            field: round(100.0 * sum(1 for e in entries if e.get(field)) / total, 1)
            for field in RSEC_FIELDS
        }
    print(f"  {'Field':<22} {'Coverage':>9}")
    print("  " + "-" * 34)
    for field, pct in coverage.items():
        print(f"  {field:<22} {pct:>8.1f}%  {_bar(pct)}")


def main() -> None:
    sources = sys.argv[1:] or ["rsec", "toolfinder"]
    for src in sources:
        src = src.lower()
        if src in ("rsec", "r"):
            report_rsec()
        elif src in ("toolfinder", "tf", "t"):
            report_toolfinder()
        else:
            print(f"Unknown source '{src}'. Use: rsec, toolfinder", file=sys.stderr)
            sys.exit(1)
        print()


if __name__ == "__main__":
    main()
