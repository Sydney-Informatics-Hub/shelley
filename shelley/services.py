"""shelley subcommands as plain functions that return results and never print/render.

Build is split based on root access:

- ``resolve`` and ``resolve_all`` run as the user: spec → one container on the mount.
  An ambiguous version is handed to ``choose`` (the CLI's prompt) here, before sudo.
- ``build_resolved`` runs where ``/apps`` is writable (root, or a test's tmp roots):
  bootstrap, plan, then apply each tag in its own transaction.

Interactive prompting and rendering stay in ``shelley.client``; this module only takes
callables for them, so it runs headless in tests.
"""

import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from difflib import get_close_matches

from .builder.shpc_settings import ensure_shared_shpc_settings
from .errors import AmbiguousTag, ShelleyError, TagRequired
from .galaxy.catalogue import GalaxyCatalogue
from .galaxy.exposer import Curate, ShpcExposer
from .results import (
    BuildResult,
    CleanResult,
    FindResult,
    Resolved,
    TagState,
    ToolMeta,
    VersionRow,
)
from .search.base import MetadataSource
from .tags import Tag, newest_first
from .utils.perms import apply_build_umask, ensure_shared_layout

Choose = Callable[[AmbiguousTag], str]

# Values that reach root must look like a tool name or a tag, never a path.
_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+\-]*")


class BuildCancelled(ShelleyError):
    def __init__(self, what: str = "Build cancelled"):
        super().__init__(f"{what}; nothing was changed.")


class InvalidSpec(ShelleyError):
    pass


def parse_spec(spec: str) -> tuple[str, str | None]:
    """``tool``, ``tool/version`` or ``tool:version`` -> (tool, version or None)."""
    for sep in ("/", ":"):
        if sep in spec:
            tool, version = spec.split(sep, 1)
            return tool, version or None
    return spec, None


def resolve(
    spec: str, catalogue: GalaxyCatalogue, choose: Choose | None = None
) -> Resolved:
    """Resolve one spec to a verified SIF. Raises the typed catalogue errors."""
    tool, requested = parse_spec(spec.strip())
    try:
        tag = catalogue.resolve(tool, requested)
    except AmbiguousTag as e:
        if choose is None:
            raise
        tag = Tag(choose(e))
    name = catalogue.name(tool)
    sif = catalogue.verify(tool, tag)
    versions = tuple(dict.fromkeys(t.version for t in catalogue.tags(tool)))
    return Resolved(
        spec, name, tag, sif, defaulted=requested is None, versions=versions
    )


def resolve_all(
    specs: Iterable[str], catalogue: GalaxyCatalogue, choose: Choose | None = None
) -> tuple[list[Resolved], list[BuildResult]]:
    """Resolve every spec; failures are returned as results, the rest carry on."""
    resolved, failed = [], []
    for spec in specs:
        try:
            resolved.append(resolve(spec, catalogue, choose))
        except ShelleyError as e:
            failed.append(BuildResult(spec, parse_spec(spec)[0], error=e))
        except ValueError:  # the version prompt was cancelled
            cancelled = BuildCancelled("Version selection cancelled")
            failed.append(BuildResult(spec, parse_spec(spec)[0], error=cancelled))
    return resolved, failed


def parse_resolved(value: str, catalogue: GalaxyCatalogue) -> Resolved:
    """Turn a ``--resolved-tag tool:tag`` value back into a verified ``Resolved``.

    Runs as root, so the value is checked against a strict pattern and the mount.
    """
    tool, sep, raw = value.partition(":")
    if not (sep and _SAFE.fullmatch(tool) and _SAFE.fullmatch(raw)):
        raise InvalidSpec(f"Invalid --resolved-tag value: {value!r}")
    tag = Tag(raw)
    return Resolved(value, catalogue.name(tool), tag, catalogue.verify(tool, tag))


def prepare_build_environment(load_build_modules: Callable[[], object]) -> None:
    """Umask, Lmod build modules, shared layout, shpc settings (idempotent)."""
    apply_build_umask()
    load_build_modules()
    ensure_shared_layout()
    ensure_shared_shpc_settings()


def build_resolved(
    items: Iterable[Resolved],
    exposer: ShpcExposer,
    curate: Curate | None = None,
    on_progress: Callable[[Resolved], object] | None = None,
) -> list[BuildResult]:
    """Plan and apply each item in its own transaction; one failure does not stop the rest."""
    results = []
    for item in items:
        if on_progress is not None:
            on_progress(item)
        try:
            try:
                plan = exposer.plan(item.tool, item.tag, item.sif, curate=curate)
            except ValueError as e:  # questionary cancellation
                raise BuildCancelled() from e
            module_path = exposer.apply(plan)
            warnings = ()
            if not plan.aliases and curate is None:
                warnings = (
                    f"{plan.uri}:{plan.tag.raw} exposes no command aliases, so the module "
                    f"has no wrapper scripts. Rebuild with -i/--interactive to add some:\n\n"
                    f"shelley build {item.tool}/{plan.tag.raw} --interactive",
                )
            results.append(
                BuildResult(
                    item.spec,
                    item.tool,
                    item.tag,
                    module_path,
                    warnings=warnings,
                    defaulted=item.defaulted,
                    versions=item.versions,
                )
            )
        except Exception as e:
            # Recorded per item; the transaction has already undone any partial writes.
            results.append(BuildResult(item.spec, item.tool, item.tag, error=e))
    return results


# ---------------------------------------------------------------------- find / search
# Opt-in with SHELLEY_NEW_DISCOVERY=1 (migration plan, batch 4).


class NotInstalled(ShelleyError):
    def __init__(self, tool: str, requested: str | None, installed: list[str]):
        self.tool, self.requested, self.installed = tool, requested, installed
        if requested is None:
            message = (
                f"shelley clean requires an explicit version, e.g. {tool}:<version>."
            )
        else:
            message = f"Version '{requested}' is not installed for '{tool}'."
        super().__init__(message)


def lookup(source: MetadataSource, name: str) -> dict | None:
    """The metadata record whose id or name is ``name`` (case-insensitive)."""
    wanted = name.lower()
    for entry in source.entries:
        if (entry.get("id") or "").lower() == wanted or (
            entry.get("name") or ""
        ).lower() == wanted:
            return entry
    return None


def find(
    query: str,
    catalogue: GalaxyCatalogue,
    source: MetadataSource,
    verbose: bool = False,
) -> FindResult:
    """Metadata, versions and install state for one tool name.

    Versions are ordered by the same rule ``build`` uses, so the top row is what
    ``shelley build <tool>`` installs (T1), and "installed" means an exact tag match (T4).
    """
    name = re.sub(r"[:/].*$", "", query).strip()
    entry = lookup(source, name)
    builds = catalogue.builds(name)
    if not builds and entry and entry.get("id"):
        builds = catalogue.builds(entry["id"])
        if builds:
            name = entry["id"]

    meta = _meta(source, entry) if entry else None
    if not builds:
        suggestions = () if entry else _suggestions(source, name)
        return FindResult(name, None, meta=meta, suggestions=suggestions)

    tool = catalogue.name(name)
    states = catalogue.installed(tool)
    loadable = {t.version for t, s in states.items() if s is TagState.LINKED}
    newest: dict[str, float] = {}
    for b in builds:  # newest tag first, so versions keep that order
        newest[b.tag.version] = max(newest.get(b.tag.version, 0.0), b.mtime)
    versions = tuple(
        VersionRow(v, format_date(mtime), v in loadable) for v, mtime in newest.items()
    )
    try:
        latest_tag: Tag | None = catalogue.resolve(tool)
    except TagRequired:
        latest_tag = None
    rows = tuple((b, states.get(b.tag)) for b in builds) if verbose else ()
    return FindResult(name, tool, meta, versions, rows, latest_tag)


def search(
    query: str, source: MetadataSource, catalogue: GalaxyCatalogue
) -> list[tuple[str, str]]:
    """(name, description) of tools matching ``query`` that have a Galaxy container."""
    ids = {t.replace("-", "_") for t in catalogue.tool_ids()}
    source.entries = [
        e
        for e in source.entries
        if (e.get("id") or "").lower().replace("-", "_") in ids
    ]
    names = source.search(query)
    described = {
        str(e.get("name") or e.get("id") or ""): str(e.get("description") or "")
        for e in source.entries
    }
    return [(n, described.get(n, "")) for n in names]


def _meta(source: MetadataSource, entry: dict) -> ToolMeta:
    return ToolMeta(
        id=entry.get("id", ""),
        name=entry.get("name") or entry.get("id", ""),
        description=entry.get("description") or "",
        homepage=entry.get("homepage") or "",
        operations=tuple(source.flatten_edam(entry.get("edam-operations"))),
        inputs=tuple(source.flatten_edam(entry.get("edam-inputs"))),
        outputs=tuple(source.flatten_edam(entry.get("edam-outputs"))),
    )


def _suggestions(source: MetadataSource, name: str) -> tuple[tuple[str, str], ...]:
    by_id = {
        e["id"].lower(): (e.get("name") or e["id"], e.get("description") or "")
        for e in source.entries
        if e.get("id")
    }
    close = get_close_matches(name.lower(), by_id.keys(), n=8, cutoff=0.6)
    return tuple(by_id[m] for m in close)


def format_date(mtime: float) -> str:
    """A snapshot mtime as ``YYYY-MM-DD`` (UTC), as ``find`` shows it."""
    return datetime.fromtimestamp(mtime, tz=UTC).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------- clean


def resolve_installed(spec: str, catalogue: GalaxyCatalogue) -> tuple[str, Tag]:
    """An explicit tool version to one installed tag (exact tag or version), as the user."""
    tool, requested = parse_spec(spec.strip())
    states = catalogue.installed(tool)
    installed = [t.raw for t in newest_first(states)]
    if requested is None:
        raise NotInstalled(tool, None, installed)
    matches = [t for t in states if t.matches(requested)]
    if not matches:
        raise NotInstalled(tool, requested, installed)
    if len(matches) > 1:
        raise AmbiguousTag(tool, requested, [t.raw for t in newest_first(matches)])
    return catalogue.name(tool), matches[0]


def clean_resolved(
    value: str, catalogue: GalaxyCatalogue, exposer: ShpcExposer
) -> CleanResult:
    """Root half of clean: validate ``tool:tag``, check it is installed, remove it."""
    tool, sep, raw = value.partition(":")
    if not (sep and _SAFE.fullmatch(tool) and _SAFE.fullmatch(raw)):
        raise InvalidSpec(f"Invalid --resolved-tag value: {value!r}")
    tag = Tag(raw)
    states = catalogue.installed(tool)
    if tag not in states:
        raise NotInstalled(tool, raw, [t.raw for t in newest_first(states)])
    return exposer.remove(catalogue.name(tool), tag)
