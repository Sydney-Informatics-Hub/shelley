"""What the Galaxy Singularity mount offers, from one source of truth (ADR 0003).

Versions come from the bundled snapshot (``galaxy_singularity_cache.json.gz``), parsed
once per catalogue. The live mount is touched only to ``stat`` the one SIF a build is
about to use, or to list it when a requested tag is missing from the snapshot, e.g. a tag
published since the last refresh. The mount has been append-only in practice, so a stale
snapshot misses new tags but does not list removed ones.

Read-only and UI-free: it raises typed errors (``shelley.errors``) and never prompts, so
it runs unprivileged and is testable against a fixture directory.
"""

import gzip
import json
from functools import cached_property
from pathlib import Path

from ..errors import AmbiguousTag, MountUnavailable, TagNotFound
from ..tags import Tag, latest, newest_first
from ..utils import globals as gl

DEFAULT_SNAPSHOT = gl.DATA_DIR / "galaxy_singularity_cache.json.gz"


def _variants(tool: str) -> list[str]:
    """Lookup keys in preference order: exact (case-insensitive), then ``-``/``_`` swapped.

    Exact first because a few tools exist under both spellings as different containers
    (``t_coffee`` and ``t-coffee``).
    """
    lower = tool.lower()
    return list(
        dict.fromkeys([lower, lower.replace("_", "-"), lower.replace("-", "_")])
    )


class GalaxyCatalogue:
    """Tags available for each tool on the Galaxy Singularity mount.

    ``snapshot`` and ``mount`` default to the bundled snapshot and the configured mount
    (``SHELLEY_CVMFS_PATH``), resolved when the catalogue is created.
    """

    def __init__(self, snapshot: Path | None = None, mount: Path | None = None):
        self.snapshot = Path(snapshot) if snapshot is not None else DEFAULT_SNAPSHOT
        self.mount = Path(mount) if mount is not None else gl.cvmfs_singularity()

    @cached_property
    def _index(self) -> dict[str, tuple[str, list[Tag]]]:
        """Lower-cased tool name -> (tool name as spelled on the mount, tags)."""
        with gzip.open(self.snapshot, "rt", encoding="utf-8") as f:
            doc = json.load(f)
        index: dict[str, tuple[str, list[Tag]]] = {}
        for entry in doc["entries"]:
            if not entry.get("tag"):  # non-container files in the mount root
                continue
            name = entry["tool_name"]
            index.setdefault(name.lower(), (name, []))[1].append(Tag(entry["tag"]))
        return index

    def _lookup(self, tool: str) -> tuple[str, list[Tag]] | None:
        for key in _variants(tool):
            if key in self._index:
                return self._index[key]
        return None

    def tool_ids(self) -> set[str]:
        """Every tool name in the snapshot, lower-cased."""
        return set(self._index)

    def name(self, tool: str) -> str:
        """The tool's name as spelled on the mount (``STAR-Fusion`` -> ``star-fusion``)."""
        found = self._lookup(tool)
        return found[0] if found else tool

    def tags(self, tool: str) -> list[Tag]:
        """Tags of ``tool`` in the snapshot, newest first. Empty if unknown."""
        found = self._lookup(tool)
        return newest_first(found[1]) if found else []

    def resolve(self, tool: str, requested: str | None = None) -> Tag:
        """The one tag a request names: the latest, an exact tag, or an exact version.

        Falls back to listing the live mount when the snapshot has no match, so tags
        published since the last refresh can still be built by name.

        Raises ``TagNotFound``, ``AmbiguousTag`` (one version, several builds),
        ``TagRequired`` (mulled container, no tag given) or ``MountUnavailable``.
        """
        candidates = self.tags(tool)
        if requested is None:
            if not candidates:
                candidates = self._live_tags(tool)
            if not candidates:
                raise TagNotFound(tool, None)
            return latest(tool, candidates)

        matches = [t for t in candidates if t.matches(requested)]
        if not matches:
            candidates = self._live_tags(tool)
            matches = [t for t in candidates if t.matches(requested)]
        if not matches:
            versions = sorted({t.version for t in candidates}, key=Tag, reverse=True)
            raise TagNotFound(tool, requested, versions)
        exact = [t for t in matches if t.raw == requested]
        if exact:
            return exact[0]
        if len(matches) > 1:
            raise AmbiguousTag(tool, requested, [t.raw for t in newest_first(matches)])
        return matches[0]

    def verify(self, tool: str, tag: Tag) -> Path:
        """Path of the SIF for ``tool:tag``, after checking it exists on the live mount."""
        if not self.mount.is_dir():
            raise MountUnavailable(self.mount)
        path = self.mount / f"{self.name(tool)}:{tag.raw}"
        if not path.exists():
            raise TagNotFound(tool, tag.raw)
        return path

    def _live_tags(self, tool: str) -> list[Tag]:
        """Tags of ``tool`` from a full listing of the mount (slow: >100k entries)."""
        if not self.mount.is_dir():
            raise MountUnavailable(self.mount)
        by_name: dict[str, list[Tag]] = {}
        for entry in self.mount.iterdir():
            name, sep, raw = entry.name.partition(":")
            if sep:
                by_name.setdefault(name.lower(), []).append(Tag(raw))
        for key in _variants(tool):
            if key in by_name:
                return newest_first(by_name[key])
        return []
