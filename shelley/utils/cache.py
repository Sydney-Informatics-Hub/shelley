"""CVMFS cache loading utilities."""

import gzip
import json
import re
from datetime import datetime, timezone

from shelley.utils.globals import DATA_DIR


def _format_mtime(mtime: float) -> str:
    """Format a unix timestamp as YYYY-MM-DD (UTC)."""
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")


def _version_key(tag: str) -> tuple:
    """Numeric sort key from the leading version of a tag (e.g. ``1.21--h50`` -> ``(1, 21)``)."""
    m = re.match(r"^(\d+(?:\.\d+)*)", tag)
    if m:
        return tuple(int(x) for x in m.group(1).split("."))
    return (0,)


def load_cvmfs_tool_ids() -> set[str] | None:
    """Return normalised tool IDs from the CVMFS container cache, or None if unavailable."""
    cache_path = DATA_DIR / "galaxy_singularity_cache.json.gz"
    if not cache_path.exists():
        return None
    with gzip.open(cache_path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["tool_name"].lower().replace("-", "_") for entry in data["entries"]}


def load_versions_from_cache(tool_name: str) -> list[tuple[str, str, float]] | None:
    """Return (tag, path, mtime) triples for tool_name from the CVMFS cache, sorted newest-first.

    Returns None if the cache file is missing; returns [] if the tool has no entries.
    """
    cache_path = DATA_DIR / "galaxy_singularity_cache.json.gz"
    if not cache_path.exists():
        return None
    with gzip.open(cache_path, "rt", encoding="utf-8") as f:
        data = json.load(f)

    tool_lower = tool_name.lower()
    variations = {
        tool_lower,
        tool_lower.replace("-", "_"),
        tool_lower.replace("_", "-"),
    }
    entries = [e for e in data["entries"] if e["tool_name"].lower() in variations]
    entries.sort(key=lambda e: _version_key(e["tag"]), reverse=True)
    return [(e["tag"], e["path"], e["mtime"]) for e in entries]


def compute_version_entries(
    tool_id: str, triples: list[tuple[str, str, float]]
) -> list[dict]:
    """Deduplicate (tag, path, mtime) triples, keeping one row per short version.

    The date reported for a version is the most recent mtime across all of that
    version's builds (a single short version may have several ``--hash`` builds).
    Version rows preserve the input order (newest version first).
    """
    latest_mtime: dict[str, float] = {}
    order: list[str] = []
    for tag, _path, mtime in triples:
        short = tag.split("--")[0]
        if short not in latest_mtime:
            order.append(short)
            latest_mtime[short] = mtime
        elif mtime > latest_mtime[short]:
            latest_mtime[short] = mtime
    return [
        {"version": short, "date": _format_mtime(latest_mtime[short])}
        for short in order
    ]


def compute_build_entries(
    tool_id: str, triples: list[tuple[str, str, float]]
) -> list[dict]:
    """Return one row per individual container build, sorted by version then build date.

    Unlike ``compute_version_entries``, this keeps every individual container build
    (a single short version may have several ``--hash`` builds) and carries the full
    CVMFS container path — used by the ``-v`` view. Rows are ordered newest-version
    first, and within a version newest-build (mtime) first.
    """
    ordered = sorted(triples, key=lambda t: (_version_key(t[0]), t[2]), reverse=True)
    return [
        {"tag": tag, "path": path, "date": _format_mtime(mtime)}
        for tag, path, mtime in ordered
    ]
