"""``shelley build`` on the new build core, the default since batch 3a.

``SHELLEY_LEGACY_BUILD=1`` selects the 0.4.0 build in ``commands/build.py`` until that
is deleted in batch 3b. Accepted arguments are the same (a spec or a tools file,
``-i``/``--interactive``), plus the hidden ``--resolved-tag tool:tag`` that the user
process passes to its root child.
"""

from datetime import datetime
from pathlib import Path

import questionary
from rich.box import ROUNDED
from rich.table import Table

from .. import privilege, services
from ..builder.guts_integration import edit_aliases_interactive
from ..errors import AmbiguousTag, ShelleyError
from ..galaxy.catalogue import GalaxyCatalogue
from ..galaxy.exposer import ShpcExposer
from ..results import BuildResult, Resolved
from ..tools.lmod import Lmod
from ..utils.style import ShelleyStyle, console, print_error, print_info, print_rule

RESOLVED_FLAG = "--resolved-tag"


def run(argv: list[str]) -> int:
    """Entry point for ``shelley build ...``; returns the process exit code."""
    interactive, resolved_values, positional = _parse(argv)
    catalogue = GalaxyCatalogue()

    if resolved_values:  # we are the root child: build exactly these tags
        try:
            items = [services.parse_resolved(v, catalogue) for v in resolved_values]
        except ShelleyError as e:
            _render_error("Build Failed", e)
            return 1
        return _apply_and_render(items, interactive, batch=len(items) > 1)

    if not positional:
        print_info(
            "Usage: [command]shelley build <tool\\[/version]> [-i|--interactive][/command]"
        )
        return 1

    path = Path(positional[0])
    batch = path.is_file()
    specs = _read_tools_file(path) if batch else [positional[0]]
    if batch and not specs:
        print_info(f"No tool specs found in '{path}' (file is empty or all comments)")
        return 1
    if batch and interactive:
        print_info(
            "-i/--interactive is not supported for a tools file; building as listed."
        )
        interactive = False

    resolved, failed = services.resolve_all(
        specs, catalogue, choose=_chooser(catalogue)
    )
    for result in failed:
        _render_error(f"Build Failed: {result.spec}", result.error)
    if not resolved:
        return 1
    for item in resolved:
        if item.defaulted and len(item.versions) > 1:
            console.print(
                ShelleyStyle.create_build_info(
                    item.tool, item.tag.raw, list(item.versions)
                )
            )

    if privilege.needs_root():
        args = ["build"]
        for item in resolved:
            args += [RESOLVED_FLAG, f"{item.tool}:{item.tag.raw}"]
        if interactive:
            args.append("--interactive")
        print_info(
            f"Running with elevated privileges: build {' '.join(r.spec for r in resolved)}"
        )
        code = privilege.reexec(args)
        return 1 if (code or failed) else 0

    code = _apply_and_render(resolved, interactive, batch=batch)
    return 1 if (code or failed) else 0


def _apply_and_render(items: list[Resolved], interactive: bool, batch: bool) -> int:
    lmod = Lmod()
    try:
        services.prepare_build_environment(lmod.load_build_modules)
    except (OSError, RuntimeError) as e:
        console.print(
            ShelleyStyle.create_error_panel(
                "Build Failed",
                str(e),
                "Check write access to the shared build directories, or set "
                "SHELLEY_SHPC_BASE to a writable location",
            )
        )
        return 1
    exposer = ShpcExposer(lmod=lmod)
    curate = edit_aliases_interactive if interactive else None
    results = []
    for item in items:
        if curate is not None:  # the alias prompts own the terminal: no spinner
            results += services.build_resolved([item], exposer, curate=curate)
            continue
        with ShelleyStyle.create_status(
            f"Building module for {item.tool}/{item.tag.raw}"
        ):
            results += services.build_resolved([item], exposer)
    for result in results:
        _render_result(result)
    if batch:
        _render_summary(results)
    return 0 if all(r.ok for r in results) else 1


# ------------------------------------------------------------------ prompts
def _chooser(catalogue: GalaxyCatalogue):
    """Pick one build when a version matches several (the 0.4.0 prompt, before sudo)."""

    def choose(err: AmbiguousTag) -> str:
        choices = []
        for raw in err.matches:
            label = raw
            try:
                st = (catalogue.mount / f"{catalogue.name(err.tool)}:{raw}").stat()
                when = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
                label = f"{raw}  ({st.st_size / 1024**2:.1f} MB, modified {when})"
            except OSError:
                pass
            choices.append(questionary.Choice(title=label, value=raw))
        try:
            selected = questionary.select(
                f"Multiple builds found for {err.tool}. Select one to install:",
                choices=choices,
            ).ask()
        except (EOFError, OSError):  # no terminal to prompt on (piped stdin, CI)
            selected = None
        if selected is None:
            raise ValueError("Version selection cancelled.")
        return selected

    return choose


# ------------------------------------------------------------------ rendering
def _render_result(result: BuildResult) -> None:
    if not result.ok:
        _render_error("Build Failed", result.error)
        return
    for warning in result.warnings:
        console.print(ShelleyStyle.create_warning_panel("No aliases", warning))
    console.print(
        ShelleyStyle.create_build_success(
            result.tool, result.tag.raw, result.module_path
        )
    )


def _render_error(title: str, error: BaseException | None) -> None:
    suggestion = ""
    if not isinstance(error, ShelleyError):
        suggestion = "Check that CVMFS is mounted and the tool exists"
    console.print(ShelleyStyle.create_error_panel(title, str(error), suggestion))


def _render_summary(results: list[BuildResult]) -> None:
    print_rule("Build Results")
    table = Table(
        title="[header]Build Summary[/header]",
        box=ROUNDED,
        border_style="border",
        header_style="table.header",
    )
    table.add_column("Tool", style="tool")
    table.add_column("Status", justify="center")
    table.add_column("Result", style="muted")
    for r in results:
        style = "status.success" if r.ok else "status.error"
        table.add_row(
            f"{r.tool}/{r.tag.raw}" if r.tag else r.spec,
            f"[{style}]{'✓' if r.ok else '✗'}[/{style}]",
            "Success" if r.ok else "Failed",
        )
    console.print(table)
    if not all(r.ok for r in results):
        print_error("Some modules failed; see the errors above.")


# ------------------------------------------------------------------ parsing
def _parse(argv: list[str]) -> tuple[bool, list[str], list[str]]:
    interactive, resolved, positional = False, [], []
    it = iter(argv)
    for arg in it:
        if arg in ("-i", "--interactive"):
            interactive = True
        elif arg == RESOLVED_FLAG:
            resolved.append(next(it, ""))
        elif arg.startswith(RESOLVED_FLAG + "="):
            resolved.append(arg.split("=", 1)[1])
        else:
            positional.append(arg)
    return interactive, resolved, positional


def _read_tools_file(path: Path) -> list[str]:
    """One spec per line; ``#`` comments and blank lines ignored (as in 0.4.0)."""
    specs = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            specs.append(line)
    return specs
