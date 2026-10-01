#!/usr/bin/env python3
"""
Build the Galaxy Singularity container cache artifact for shelley find/search.

Scans the Galaxy Project Singularity mirror on CVMFS
(/cvmfs/singularity.galaxyproject.org/all), materialising one entry per
tool:tag container into the galaxy_singularity_cache.json.gz artifact consumed
by shelley find and shelley search.

Usage:
    shelley-build-galaxy [options]
    python -m shelley.scripts.build_galaxy_cache [options]

Options:
    --cvmfs-root      CVMFS 'all' directory to scan (default: the Galaxy mirror)
    --out             Output path (default: shelley/data/galaxy_singularity_cache.json.gz)
    -v/--verbose      Debug logging
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, TypedDict

from shelley.utils.globals import CVMFS_GALAXY_SINGULARITY_PATH, DATA_DIR

log = logging.getLogger("build-galaxy-cache")

DEFAULT_OUT = DATA_DIR / "galaxy_singularity_cache.json.gz"
DEFAULT_CVMFS = Path(CVMFS_GALAXY_SINGULARITY_PATH)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class CacheEntry(TypedDict):
    entry_name: str
    tool_name: str
    tag: Optional[str]
    path: str
    size_bytes: int
    mtime: float


class CacheDocument(TypedDict):
    generated_at: str
    cvmfs_root: str
    entry_count: int
    entries: List[CacheEntry]
    tool_names: List[str]


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def scan_entries(cvmfs_path: Path) -> list[CacheEntry]:
    """Scan a CVMFS 'all' directory into CacheEntry records.

    Each child is a ``tool:tag`` container directory; the name is split on the
    first ``:`` into tool_name/tag. Entries that fail to ``stat()`` are logged
    and skipped so a single bad path does not abort the full scan.
    """
    log.info("Scanning %s for containers ...", cvmfs_path)
    entries: list[CacheEntry] = []

    for entry in cvmfs_path.iterdir():
        if ":" in entry.name:
            tool_name, tag = entry.name.split(":", 1)
        else:
            tool_name, tag = entry.name, None

        try:
            st = entry.stat()
        except OSError as exc:
            log.warning("Skipping %s: %s", entry, exc)
            continue

        entries.append(
            CacheEntry(
                entry_name=entry.name,
                tool_name=tool_name,
                tag=tag,
                path=str(entry),
                size_bytes=st.st_size,
                mtime=st.st_mtime,
            )
        )
        if len(entries) % 10000 == 0:
            log.debug("Scanned %d entries ...", len(entries))

    log.info("Scanned %d entries", len(entries))
    return entries


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_artifact(entries: list[CacheEntry], cvmfs_root: Path, out_path: Path) -> None:
    tool_names = sorted({e["tool_name"] for e in entries})
    doc: CacheDocument = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cvmfs_root": str(cvmfs_root),
        "entry_count": len(entries),
        "entries": entries,
        "tool_names": tool_names,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    log.info("Wrote %d entries → %s", len(entries), out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Galaxy Singularity container cache artifact for shelley find/search."
    )
    parser.add_argument(
        "--cvmfs-root",
        type=Path,
        default=DEFAULT_CVMFS,
        help=f"CVMFS 'all' directory to scan (default: {DEFAULT_CVMFS})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path (default: {DEFAULT_OUT})",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [build-galaxy-cache] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.cvmfs_root.is_dir():
        parser.error(f"CVMFS root not found or not a directory: {args.cvmfs_root}")

    entries = scan_entries(args.cvmfs_root)
    write_artifact(entries, args.cvmfs_root, args.out)

    print(f"\nArtifact : {args.out}")
    print(f"Entries  : {len(entries)}")
    print(f"Tools    : {len(set(e['tool_name'] for e in entries))}")


if __name__ == "__main__":
    main()
