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

from .builder.shpc_settings import ensure_shared_shpc_settings
from .errors import AmbiguousTag, ShelleyError
from .galaxy.catalogue import GalaxyCatalogue
from .galaxy.exposer import Curate, ShpcExposer
from .results import BuildResult, Resolved
from .tags import Tag
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
        except (
            Exception
        ) as e:  # recorded per item; the transaction has already undone it
            results.append(BuildResult(item.spec, item.tool, item.tag, error=e))
    return results
