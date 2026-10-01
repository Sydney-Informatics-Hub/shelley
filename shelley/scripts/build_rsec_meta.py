#!/usr/bin/env python3
"""
Build the RSEC bio.tools metadata artifact for shelley search.

Fetches *.biotools.json files from the research-software-ecosystem/content
GitHub repository, parses them into the rsec_meta.json.gz artifact consumed
by shelley search.

Usage:
    shelley-build-rsec [options]
    python -m shelley.scripts.build_rsec_meta [options]

Options:
    --assess          Print field-coverage report and exit without writing
    --method          sparse-clone (default) or tarball
    --ref             Branch/tag to fetch (default: master)
    --out             Output path (default: shelley/data/rsec_meta.json.gz)
    --workdir         Persistent temp directory (auto by default)
    -v/--verbose      Debug logging
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shelley.utils.globals import DATA_DIR

log = logging.getLogger("build-rsec-meta")

DEFAULT_OUT = DATA_DIR / "rsec_meta.json.gz"
REPO_URL = "https://github.com/research-software-ecosystem/content"
DEFAULT_REF = "master"


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------


def _fetch_sparse_clone(repo_url: str, ref: str, workdir: Path) -> Path:
    clone_dir = workdir / "content"
    log.info("Sparse-cloning %s@%s ...", repo_url, ref)
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            "--branch",
            ref,
            repo_url,
            str(clone_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(clone_dir), "sparse-checkout", "set", "data"],
        check=True,
        capture_output=True,
        text=True,
    )
    return clone_dir / "data"


def _fetch_tarball(repo_url: str, ref: str, workdir: Path) -> Path:
    url = f"{repo_url}/archive/refs/heads/{ref}.tar.gz"
    archive_path = workdir / "content.tar.gz"
    log.info("Downloading tarball from %s ...", url)
    urllib.request.urlretrieve(url, archive_path)

    extract_dir = workdir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    log.info("Extracting data/ from tarball ...")
    with tarfile.open(archive_path, "r:gz") as tf:
        members = [
            m
            for m in tf.getmembers()
            if "/data/" in m.name and m.name.endswith(".biotools.json")
        ]
        tf.extractall(path=extract_dir, members=members, filter="data")

    for candidate in extract_dir.glob("*/data"):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate data/ inside extracted tarball")


def fetch_content(repo_url: str, ref: str, method: str, workdir: Path) -> Path:
    """Return path to the data/ directory, fetching as needed."""
    if method == "sparse-clone":
        try:
            return _fetch_sparse_clone(repo_url, ref, workdir)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            log.warning("Sparse clone failed (%s); falling back to tarball.", exc)
            return _fetch_tarball(repo_url, ref, workdir)
    return _fetch_tarball(repo_url, ref, workdir)


def _source_commit(data_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(data_dir.parent), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _flatten_terms(items: Any) -> list[str]:
    """Extract EDAM term strings from a list of {term, uri} dicts or plain strings."""
    out: list[str] = []
    if not items:
        return out
    if not isinstance(items, list):
        items = [items]
    for item in items:
        if isinstance(item, dict):
            t = item.get("term") or item.get("uri", "")
            if t:
                out.append(str(t))
        elif item:
            out.append(str(item))
    return list(dict.fromkeys(out))


def _parse_functions(functions: Any) -> tuple[list[str], list[str], list[str]]:
    """Extract (operations, inputs, outputs) from the bio.tools function[] array."""
    operations: list[str] = []
    inputs: list[str] = []
    outputs: list[str] = []

    for fn in functions or []:
        operations.extend(_flatten_terms(fn.get("operation")))
        for inp in fn.get("input") or []:
            data = inp.get("data") or {}
            t = data.get("term") or data.get("uri", "")
            if t:
                inputs.append(str(t))
            inputs.extend(_flatten_terms(inp.get("format")))
        for out in fn.get("output") or []:
            data = out.get("data") or {}
            t = data.get("term") or data.get("uri", "")
            if t:
                outputs.append(str(t))
            outputs.extend(_flatten_terms(out.get("format")))

    return (
        list(dict.fromkeys(operations)),
        list(dict.fromkeys(inputs)),
        list(dict.fromkeys(outputs)),
    )


def parse_biotools_json(path: Path) -> dict | None:
    """Parse one *.biotools.json file into the entry schema; return None to skip."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.debug("Skipping %s: %s", path, exc)
        return None

    biotools_id = raw.get("biotoolsID") or raw.get("biotoolsid") or ""
    name = raw.get("name") or ""
    if not biotools_id or not name:
        return None

    topics = _flatten_terms(raw.get("topic"))
    operations, inputs, outputs = _parse_functions(raw.get("function"))

    return {
        "id": biotools_id.lower(),
        "name": name,
        "biotools_id": biotools_id,
        "description": (raw.get("description") or "").strip(),
        "homepage": raw.get("homepage") or "",
        "license": raw.get("license") or "",
        "edam-operations": operations,
        "edam-topics": topics,
        "edam-inputs": inputs,
        "edam-outputs": outputs,
    }


def build_entries(data_dir: Path) -> list[dict]:
    """Walk data_dir, parse all *.biotools.json, dedupe by id (first wins)."""
    log.info("Scanning %s for *.biotools.json files ...", data_dir)
    seen: dict[str, dict] = {}
    for json_path in sorted(data_dir.rglob("*.biotools.json")):
        entry = parse_biotools_json(json_path)
        if entry and entry["id"] not in seen:
            seen[entry["id"]] = entry
    log.info("Parsed %d unique entries", len(seen))
    return sorted(seen.values(), key=lambda e: e["id"])


# ---------------------------------------------------------------------------
# Coverage assessment
# ---------------------------------------------------------------------------

ASSESSED_FIELDS = [
    "name",
    "description",
    "homepage",
    "license",
    "edam-operations",
    "edam-topics",
    "edam-inputs",
    "edam-outputs",
]


def assess_coverage(entries: list[dict]) -> dict[str, float]:
    if not entries:
        return {}
    total = len(entries)
    return {
        field: round(100.0 * sum(1 for e in entries if e.get(field)) / total, 1)
        for field in ASSESSED_FIELDS
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_artifact(
    entries: list[dict],
    coverage: dict[str, float],
    source_commit: str,
    repo_url: str,
    ref: str,
    out_path: Path,
) -> None:
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": repo_url,
        "source_ref": ref,
        "source_commit": source_commit,
        "entry_count": len(entries),
        "field_coverage": coverage,
        "entries": entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    log.info("Wrote %d entries → %s", len(entries), out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_assessment(entries: list[dict], coverage: dict[str, float]) -> None:
    print(f"\nField coverage ({len(entries)} entries):")
    print(f"  {'Field':<22} {'Coverage':>9}")
    print("  " + "-" * 33)
    for field, pct in coverage.items():
        bar = "#" * int(pct / 5)
        print(f"  {field:<22} {pct:>8.1f}%  {bar}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RSEC bio.tools metadata artifact for shelley search."
    )
    parser.add_argument(
        "--repo-url",
        default=REPO_URL,
        help=f"GitHub repo URL (default: {REPO_URL})",
    )
    parser.add_argument(
        "--ref",
        default=DEFAULT_REF,
        help=f"Branch/tag to fetch (default: {DEFAULT_REF})",
    )
    parser.add_argument(
        "--method",
        choices=["sparse-clone", "tarball"],
        default="sparse-clone",
        help="Fetch method; sparse-clone falls back to tarball on failure (default: sparse-clone)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="Persistent temp directory — if omitted, a temp dir is created and cleaned up",
    )
    parser.add_argument(
        "--assess",
        action="store_true",
        help="Print field-coverage report and exit without writing the artifact",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [build-rsec-meta] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.workdir:
        args.workdir.mkdir(parents=True, exist_ok=True)
        _run(fetch_content(args.repo_url, args.ref, args.method, args.workdir), args)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = fetch_content(args.repo_url, args.ref, args.method, Path(tmpdir))
            _run(data_dir, args)


def _run(data_dir: Path, args: argparse.Namespace) -> None:
    entries = build_entries(data_dir)
    coverage = assess_coverage(entries)

    if args.assess:
        _print_assessment(entries, coverage)
        return

    source_commit = _source_commit(data_dir)
    write_artifact(entries, coverage, source_commit, args.repo_url, args.ref, args.out)

    print(f"\nArtifact : {args.out}")
    print(f"Entries  : {len(entries)}")
    print(f"Commit   : {source_commit}")
    _print_assessment(entries, coverage)


if __name__ == "__main__":
    main()
