#!/usr/bin/env python3
"""
Compare regenerated data artifacts against the committed versions.

Artifacts include rsec_meta.json.gz and galaxy_singularity_cache.json.gz.
The builders stamp each artifact with ``generated_at``, and gzip records its own
timestamp, so a regenerated file always differs byte-for-byte even when nothing
upstream changed. This compares content instead: ``generated_at`` is dropped and
Galaxy cache entries are sorted (directory listing order is not guaranteed).

Files whose content is unchanged are restored with ``git checkout`` so only real
changes are committed. A Markdown summary is printed to stdout.

Usage:
    python .github/scripts/compare_data.py FILE [FILE ...]

Exit status is 0 either way; ``changed=true|false`` is appended to
``$GITHUB_OUTPUT`` when it is set.
"""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
from pathlib import Path


def committed(path: str) -> bytes | None:
    """Return the file's content at HEAD, or None if it is new."""
    result = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True)
    return result.stdout if result.returncode == 0 else None


def normalise(raw: bytes, path: str) -> object:
    """Parse an artifact into a comparable form."""
    if not path.endswith(".json.gz"):
        return raw
    doc = json.loads(gzip.decompress(raw))
    doc.pop("generated_at", None)
    entries = doc.get("entries")
    if entries and "entry_name" in entries[0]:
        entries.sort(key=lambda e: e["entry_name"])
    return doc


def entry_count(raw: bytes, path: str) -> str:
    if not path.endswith(".json.gz"):
        return "—"
    return f"{json.loads(gzip.decompress(raw)).get('entry_count', '?'):,}"


def main() -> None:
    rows = []
    any_changed = False

    for path in sys.argv[1:]:
        new = Path(path).read_bytes()
        old = committed(path)

        if old is not None and normalise(old, path) == normalise(new, path):
            subprocess.run(["git", "checkout", "--", path], check=True)
            status = "unchanged"
        else:
            any_changed = True
            status = "**updated**"

        before = entry_count(old, path) if old is not None else "new"
        rows.append(f"| `{path}` | {status} | {before} | {entry_count(new, path)} |")

    print("| File | Status | Entries before | Entries after |")
    print("|---|---|---|---|")
    print("\n".join(rows))

    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as f:
            f.write(f"changed={str(any_changed).lower()}\n")


if __name__ == "__main__":
    main()
