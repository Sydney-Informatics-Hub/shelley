"""Plain data passed between the build core, the services and the renderers."""

from dataclasses import dataclass, field
from pathlib import Path

from .galaxy.registry import Marker
from .tags import Tag


@dataclass(frozen=True)
class Resolved:
    """A tool spec resolved, as the user, to one container on the mount."""

    spec: str  # what the user typed, e.g. "samtools/1.21"
    tool: str  # name as spelled on the mount
    tag: Tag
    sif: Path
    defaulted: bool = False  # no version was given, so "latest" was chosen
    versions: tuple[str, ...] = ()  # available versions, newest first (for messages)


@dataclass(frozen=True, eq=False)
class BuildPlan:
    """Everything a build will write, decided before anything is written (ADR 0005)."""

    tool: str
    tag: Tag
    uri: str
    sif: Path
    in_upstream: bool
    aliases: list[dict]
    local_entry: dict | None  # container.yaml to write, or None to leave it alone
    marker: Marker | None
    remove_legacy: bool  # drop a <=0.4.0 local entry nothing depends on
    replace_existing: bool  # this tag is already installed: move it aside first


@dataclass(frozen=True)
class BuildResult:
    spec: str
    tool: str
    tag: Tag | None = None
    module_path: Path | None = None
    error: Exception | None = None
    warnings: tuple[str, ...] = ()
    defaulted: bool = False
    versions: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return self.error is None
