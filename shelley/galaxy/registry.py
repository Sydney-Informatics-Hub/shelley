"""shpc registry entries: upstream (read-only) and shelley's local registry (ADR 0006).

``RegistryClient.fetch`` returns the upstream ``container.yaml`` for a URI, ``None`` if
the URI is not in the upstream registry, and raises ``NetworkUnavailable`` if GitHub
cannot be reached. That third case used to read as "not upstream" (T6).

``LocalRegistry`` holds shelley-authored entries only, never caches of upstream ones. Its
on-disk format (``<uri>/container.yaml`` plus ``<uri>/<tag>/aliases.yaml`` markers) is
unchanged from 0.4.0, so the old ``clean`` keeps working on entries written here.

shpc uses the *first* registry with an entry for a name, then fails if the requested tag
is missing from it (shpc/main/registry/__init__.py, shpc/main/modules/module.py). So a
local entry shadows upstream for every tag of its tool, and is refreshed with the
upstream tags on each build (``merged_with_upstream``).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..tools import net
from ..utils import globals as gl
from ..utils.perms import ensure_shared_dir, share_file

UPSTREAM_RAW = "https://raw.githubusercontent.com/singularityhub/shpc-registry/main"

# The tag value written for local entries. shpc requires a string and ignores the value
# when installing a local image with --keep-path (shpc/main/modules/module.py), so the
# SIF is no longer hashed.
LOCAL_TAG_VALUE = "local:keep-path"


class RegistryClient:
    """Reads entries from the upstream singularityhub/shpc-registry."""

    def __init__(
        self,
        base_url: str = UPSTREAM_RAW,
        fetch: Callable[[str], str | None] = net.fetch_text,
    ):
        self.base_url, self._fetch = base_url.rstrip("/"), fetch

    def fetch(self, uri: str) -> dict | None:
        """The upstream entry for ``uri``, or ``None`` if it is not upstream."""
        text = self._fetch(f"{self.base_url}/{uri}/container.yaml")
        if text is None:
            return None
        return yaml.safe_load(text) or None


@dataclass(frozen=True)
class Marker:
    """``<uri>/<tag>/aliases.yaml``: one tag's own aliases (the entry's are shared)."""

    tag: str
    aliases: list[dict] = field(default_factory=list)
    in_upstream: bool = False

    def as_yaml(self) -> dict:
        return {
            "version": self.tag,
            "aliases": self.aliases,
            "in_upstream": self.in_upstream,
        }


class LocalRegistry:
    """shelley-authored entries under the local shpc registry (``SHELLEY_LOCAL_REGISTRY``)."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else gl.local_registry()

    def entry_dir(self, uri: str) -> Path:
        return self.root / uri

    def read(self, uri: str) -> dict | None:
        path = self.entry_dir(uri) / "container.yaml"
        if not path.is_file():
            return None
        with open(path) as f:
            return yaml.safe_load(f) or None

    def markers(self, uri: str) -> dict[str, Marker]:
        """Marker per tag; an unreadable marker counts as present with defaults."""
        found: dict[str, Marker] = {}
        entry = self.entry_dir(uri)
        if not entry.is_dir():
            return found
        for d in entry.iterdir():
            if not d.is_dir():
                continue
            data = {}
            snapshot = d / "aliases.yaml"
            if snapshot.is_file():
                with open(snapshot) as f:
                    data = yaml.safe_load(f) or {}
            found[d.name] = Marker(
                d.name,
                list(data.get("aliases") or []),
                bool(data.get("in_upstream", False)),
            )
        return found

    def write(self, uri: str, entry: dict, marker: Marker | None = None) -> None:
        """Write ``container.yaml`` and, if given, the tag's marker, world-readable."""
        entry_dir = self.entry_dir(uri)
        ensure_shared_dir(entry_dir)
        path = entry_dir / "container.yaml"
        with open(path, "w") as f:
            yaml.dump(entry, f, default_flow_style=False, sort_keys=False)
        share_file(path)
        if marker is not None:
            marker_dir = entry_dir / marker.tag
            ensure_shared_dir(marker_dir)
            snapshot = marker_dir / "aliases.yaml"
            with open(snapshot, "w") as f:
                yaml.dump(
                    marker.as_yaml(), f, default_flow_style=False, sort_keys=False
                )
            share_file(snapshot)

    def is_legacy(self, uri: str, linked_tags: Iterable[str]) -> bool:
        """True for an entry left by shelley <= 0.4.0 that nothing depends on.

        That is: the entry exists, has no marker directories, and none of its tags is
        currently linked as a module. Such entries were upstream caches or Tier 0
        artefacts; the next build of the tool removes them (target-state §5).
        """
        entry = self.read(uri)
        if entry is None or self.markers(uri):
            return False
        return not set(entry.get("tags") or {}) & set(linked_tags)


def merged_with_upstream(local: dict, upstream: dict | None) -> dict:
    """``local`` with every upstream tag added; local values win for tags in both.

    Keeps a shelley-authored entry from hiding newer upstream tags of the same tool,
    since shpc stops at the first registry that has the name.
    """
    merged = dict(local)
    tags = dict((upstream or {}).get("tags") or {})
    tags.update(local.get("tags") or {})
    merged["tags"] = tags
    return merged
