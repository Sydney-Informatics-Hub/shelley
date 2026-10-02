#!/usr/bin/env python3
"""
Cross-reference the regression tool matrix against both metadata corpora.

Reports which tools are present in RSEC and toolfinder, and how many EDAM
terms are populated per field. Reads the committed artifacts — no network required.

Usage:
    python3 shelley/scripts/assess_regression_tools.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TOOLS = [
    "fastqc",
    "multiqc",
    "salmon",
    "bcftools",
    "bwa-mem2",
    "fastp",
    "sambamba",
    "samblaster",
    "samtools",
    "blast",
    "star",
    "star-fusion",
    "seurat",
    "parabricks",
    "tidyverse",
]


def _load_rsec() -> dict[str, dict]:
    path = DATA_DIR / "rsec_meta.json.gz"
    with gzip.open(path, "rt") as f:
        doc = json.load(f)
    return {e["id"]: e for e in doc["entries"]}


def _load_toolfinder() -> dict[str, dict]:
    path = DATA_DIR / "toolfinder_meta.yaml"
    with open(path) as f:
        entries = yaml.safe_load(f)
    return {e["id"].lower(): e for e in entries if e.get("id")}


def _lookup_rsec(rsec: dict, tool: str) -> dict | None:
    return rsec.get(tool) or rsec.get(tool.replace("-", ""))


def _lookup_tf(tf: dict, tool: str) -> dict | None:
    return (
        tf.get(tool) or tf.get(tool.replace("-", "_")) or tf.get(tool.replace("-", ""))
    )


def _count(lst) -> str:
    return str(len(lst)) if lst else "—"


def main() -> None:
    rsec = _load_rsec()
    tf = _load_toolfinder()

    print(
        f"{'Tool':<16} {'RSEC':<6} {'TF':<6} {'ops':<5} {'topics':<8} {'inputs':<8} outputs"
    )
    print("-" * 62)
    for tool in TOOLS:
        e = _lookup_rsec(rsec, tool)
        t = _lookup_tf(tf, tool)
        r = "✓" if e else "—"
        f = "✓" if t else "—"
        if e:
            row = (
                f"{_count(e['edam-operations']):<5}"
                f"{_count(e['edam-topics']):<8}"
                f"{_count(e['edam-inputs']):<8}"
                f"{_count(e['edam-outputs'])}"
            )
        else:
            row = "—    —       —       —"
        print(f"{tool:<16} {r:<6} {f:<6} {row}")


if __name__ == "__main__":
    main()
