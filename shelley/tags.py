"""Container tags as values, with one ordering rule for every command (ADR 0002).

A Galaxy SIF is named ``<tool>:<tag>``; the tag is usually Bioconda's
``<version>--<build string>`` (``1.21--h50ea8bc_3``). Tags are ordered with conda's own
version ordering, which is what Bioconda uses to resolve versions. ``packaging.version``
does not fit: tags are not PEP 440.

shelley-specific rules on top of conda's:

- A leading ``v`` is not part of the version, so ``v1.0`` and ``1.0`` are the same version.
- Tags that are not versions (``latest``, ``broken``, ``date.*``) are never chosen as
  latest; neither are tags conda cannot parse.
- ``mulled-*`` containers are tagged with content hashes, so they have no "latest" and a
  tag must be given explicitly.
- A requested version matches a tag exactly or by its version part, never by prefix.

Known gap, accepted: conda treats a ``p1`` suffix as a pre-release, so ``3.1p1`` sorts
before ``3.1`` (two tools in the Galaxy cache).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property

from ._vendor.conda_version import InvalidVersionSpec, VersionOrder
from .errors import TagRequired

NON_VERSIONS = frozenset({"latest", "broken"})

_V_PREFIX = re.compile(r"^v\.?(?=\d)", re.IGNORECASE)
_BUILD_NUMBER = re.compile(r"_(\d+)$")


@dataclass(frozen=True)
class Tag:
    """One container tag, e.g. ``Tag("1.21--h50ea8bc_3")``.

    Equality is by the full tag: two builds of the same version are different
    containers. Ordering (``<``, ``max``, ``sorted``) is newest-last by the rules above.
    """

    raw: str

    @cached_property
    def version(self) -> str:
        """The version part, without a leading ``v``: ``v1.0--0`` -> ``1.0``."""
        return _V_PREFIX.sub("", self.raw.split("--", 1)[0])

    @cached_property
    def build(self) -> str | None:
        """The build string after ``--``, if any: ``1.21--h50ea8bc_3`` -> ``h50ea8bc_3``."""
        _, sep, build = self.raw.partition("--")
        return build if sep else None

    @cached_property
    def _order(self) -> VersionOrder | None:
        try:
            return VersionOrder(self.version)
        except InvalidVersionSpec:
            return None

    @property
    def is_release(self) -> bool:
        """True if this tag names an orderable version (not ``latest``, ``broken``, …)."""
        v = self.version.lower()
        return (
            v not in NON_VERSIONS
            and not v.startswith("date.")
            and self._order is not None
        )

    def same_version(self, other: "Tag") -> bool:
        return self.version == other.version

    def matches(self, requested: str) -> bool:
        """True if ``requested`` names this tag exactly or names its version."""
        return requested == self.raw or _V_PREFIX.sub("", requested) == self.version

    def _build_number(self) -> int:
        match = _BUILD_NUMBER.search(self.build or "")
        return int(match.group(1)) if match else -1

    def __lt__(self, other: "Tag") -> bool:
        if not isinstance(other, Tag):
            return NotImplemented
        if self.is_release != other.is_release:
            return not self.is_release  # non-versions sort below every release
        if self.is_release and self._order != other._order:
            return bool(self._order < other._order)
        if not self.is_release and self.version != other.version:
            return self.version < other.version
        # Same version: the higher Bioconda build number is the newer build; then prefer
        # the plain spelling (``1.0`` over ``v1.0``) so the choice is stable and tidy.
        return self._tiebreak() < other._tiebreak()

    def _tiebreak(self) -> tuple[int, bool, str]:
        return (self._build_number(), not _V_PREFIX.match(self.raw), self.raw)

    def __str__(self) -> str:
        return self.raw


def newest_first(tags: Iterable[Tag]) -> list[Tag]:
    return sorted(tags, reverse=True)


def latest(tool: str, tags: Iterable[Tag]) -> Tag:
    """The newest tag of ``tool``.

    Raises ``TagRequired`` for ``mulled-*`` containers, and ``ValueError`` if there are
    no tags at all (callers check for that first and raise ``TagNotFound``).
    """
    tags = list(tags)
    if not tags:
        raise ValueError(f"no tags for {tool}")
    if is_unordered(tool):
        raise TagRequired(tool, [t.raw for t in newest_first(tags)])
    return max(tags)


def is_unordered(tool: str) -> bool:
    """mulled-v1/v2 containers are tagged by content hash and have no version order."""
    return tool.lower().startswith("mulled-")
