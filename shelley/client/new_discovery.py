"""``shelley find``, ``search`` and ``clean`` on the new core, opt-in with
``SHELLEY_NEW_DISCOVERY=1`` (migration plan, batch 4).

Parallel change: these run beside the 0.4.0 commands until the default switches. Output
keeps 0.4.0's layout; what changes is where the data comes from:

- ``find`` orders versions with the same rule as ``build``, so its top row and its
  "shelley build <tool>" hint name the version a build would install (T1), and its
  installed ticks match tags exactly, never by prefix (T4).
- ``clean`` resolves the tag before ``sudo``, then removes it all-or-nothing, leftovers
  included, so it never leaves an orphan.
"""

import questionary
from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table

from .. import privilege, services
from ..errors import AmbiguousTag, ShelleyError
from ..galaxy.catalogue import GalaxyCatalogue
from ..galaxy.exposer import ShpcExposer
from ..results import FindResult, TagState
from ..search.rsec import RsecSource
from ..tools.lmod import Lmod
from ..utils.args import parse_force_flag, parse_verbose
from ..utils.render import paginate, print_find_hint, render_tool_table
from ..utils.style import ShelleyStyle, console, print_info, print_warning

RESOLVED_FLAG = "--resolved-tag"


# ------------------------------------------------------------------ find
def run_find(argv: list[str]) -> int:
    verbose, positional = parse_verbose(argv)
    if not positional:
        print_info("Usage: [command]shelley find <tool_name> [-v][/command]")
        return 1
    with ShelleyStyle.create_status(f"Searching for tool: {positional[0]}"):
        result = services.find(
            positional[0], GalaxyCatalogue(), RsecSource().load(), verbose=verbose
        )
    _render_find(result, verbose)
    return 0


def _render_find(result: FindResult, verbose: bool) -> None:
    if not result.found:
        if result.suggestions:
            render_tool_table(
                list(result.suggestions),
                f"[warning]No exact match for '[tool]{result.query}[/tool]'. Did you mean:[/warning]",
                border_style="warning",
            )
            print_find_hint()
        else:
            console.print(
                ShelleyStyle.create_error_panel(
                    "Tool Not Found",
                    f"No tool or container matching '{result.query}' was found.",
                    "Try: shelley search <description>",
                )
            )
        return

    meta = result.meta
    lines = []
    if meta:
        for label, value in (
            ("Description", meta.description),
            ("Homepage", meta.homepage),
            ("Operations", ", ".join(meta.operations)),
            ("Inputs", ", ".join(meta.inputs)),
            ("Outputs", ", ".join(meta.outputs)),
        ):
            if value:
                style = "info" if label == "Homepage" else "muted"
                lines.append(f"[header]{label}[/header]  [{style}]{value}[/{style}]\n")
    title = meta.name if meta else result.query
    console.print(
        Panel(
            "\n".join(lines) or "[muted]No metadata available for this tool.[/muted]",
            title=f"[tool]{title}[/tool]",
            box=ROUNDED,
            border_style="primary",
            padding=(1, 2),
        )
    )

    if not result.versions:
        console.print(
            ShelleyStyle.create_warning_panel(
                "No Containers Available",
                "No Singularity containers found for this tool in CVMFS.",
            )
        )
        return

    def glyph(flag: bool) -> str:
        return "[success]✓[/success]" if flag else "[muted]✗[/muted]"

    if verbose:

        def render_page(items, page, total_pages, total):
            info = f" — page {page + 1} of {total_pages}" if total_pages > 1 else ""
            table = _table(f"[header]Available Builds ({total} total){info}[/header]")
            table.add_column("Container Path", style="accent", overflow="fold")
            for build, state in items:
                table.add_row(
                    build.tag.raw,
                    f"[muted]{services.format_date(build.mtime)}[/muted]",
                    glyph(state is TagState.LINKED),
                    str(build.path),
                )
            console.print(table)

        paginate(list(result.builds), render_page)
    else:
        shown = result.versions[:5]
        table = _table("[header]Available Versions[/header]")
        for row in shown:
            table.add_row(
                row.version, f"[muted]{row.date}[/muted]", glyph(row.installed)
            )
        if len(result.versions) > len(shown):
            table.add_row(
                f"[muted]+ {len(result.versions) - len(shown)} more[/muted]",
                "",
                f"[muted]shelley find {result.query.lower()} -v[/muted]",
            )
        console.print(table)
    console.print(
        "[muted]Installed ✓: This version is already available to module load on this system.[/muted]"
    )

    if result.latest is None:  # mulled: no "latest"
        text = (
            f"{title} has no version order; build a specific tag, e.g.:\n\n"
            f"[command]shelley build {result.tool}:{result.versions[0].version}[/command]"
        )
    else:
        text = (
            f"To install the latest version of {title} ({result.latest.version}), run:\n\n"
            f"[command]shelley build {result.tool}[/command]\n\n"
            f"To install a specific version of {title}, run:\n\n"
            f"[command]shelley build {result.tool}/{result.latest.version}[/command]"
        )
    console.print(
        Panel(
            text,
            title="[header]Install[/header]",
            box=ROUNDED,
            border_style="info",
            padding=(0, 2),
        )
    )


def _table(title: str) -> Table:
    table = Table(
        title=title,
        box=ROUNDED,
        border_style="primary",
        header_style="table.header",
        show_lines=False,
    )
    table.add_column("Versions", style="version", no_wrap=True)
    table.add_column("Date", no_wrap=True)
    table.add_column("Installed", no_wrap=True)
    return table


# ------------------------------------------------------------------ search
def run_search(argv: list[str]) -> int:
    if not argv:
        print_warning("Missing search terms")
        print_info("Usage: [command]shelley search <description>[/command]")
        return 1
    query = " ".join(argv)
    with ShelleyStyle.create_status(f"Searching for: {query}"):
        try:
            source = RsecSource().load()
        except FileNotFoundError:
            console.print(
                ShelleyStyle.create_error_panel(
                    "Corpus Not Found",
                    "rsec_meta.json.gz is missing.",
                    "Run: shelley-build-rsec",
                )
            )
            return 1
        results = services.search(query, source, GalaxyCatalogue())
    if not results:
        console.print(
            ShelleyStyle.create_error_panel(
                "No Results",
                f"No tools matched '{query}'.",
                "Try broader terms — e.g. 'alignment' instead of 'short-read alignment'",
            )
        )
        return 0

    def render_page(items, page, total_pages, total):
        info = f" — page {page + 1} of {total_pages}" if total_pages > 1 else ""
        suffix = "es" if total != 1 else ""
        render_tool_table(
            items,
            f"[header]Results for '[tool]{query}[/tool]' ({total} match{suffix}){info}[/header]",
        )
        print_find_hint(source_note="RSEC bio.tools (CVMFS-available tools)")

    paginate(results, render_page)
    return 0


# ------------------------------------------------------------------ clean
def run_clean(argv: list[str]) -> int:
    force, rest = parse_force_flag(argv)
    resolved, positional = _split_resolved(rest)
    catalogue = GalaxyCatalogue()

    if resolved:  # the root child: remove exactly this tag
        return _remove(resolved, catalogue)

    if not positional:
        print_info("Usage: [command]shelley clean <tool>:<version> [-y][/command]")
        return 1
    try:
        tool, tag = services.resolve_installed(positional[0], catalogue)
    except (services.NotInstalled, AmbiguousTag) as e:
        _render_not_installed(e)
        return 1

    if not force and not _confirm(tool, tag.raw):
        print_warning("Clean cancelled; nothing was removed.")
        return 1

    value = f"{tool}:{tag.raw}"
    if privilege.needs_root():
        print_info(f"Running with elevated privileges: clean {value}")
        return privilege.reexec(["clean", RESOLVED_FLAG, value, "-y"])
    return _remove(value, catalogue)


def _remove(value: str, catalogue: GalaxyCatalogue) -> int:
    lmod = Lmod()
    try:
        services.prepare_build_environment(lmod.load_build_modules)
        with ShelleyStyle.create_status(f"Removing {value}"):
            result = services.clean_resolved(value, catalogue, ShpcExposer(lmod=lmod))
    except (ShelleyError, OSError, RuntimeError) as e:
        console.print(
            ShelleyStyle.create_error_panel(
                "Clean Failed", str(e), "Nothing was removed."
            )
        )
        return 1
    removed = "\n".join(f"  [muted]• {item}[/muted]" for item in result.removed) or (
        "  [muted]• nothing further to remove[/muted]"
    )
    console.print(
        Panel(
            f"[status.success]✅ Module Removed[/status.success]\n\n"
            f"[header]Tool:[/header] [tool]{result.tool}[/tool]\n"
            f"[header]Version:[/header] [version]{result.tag.raw}[/version]\n\n"
            f"[header]Removed:[/header]\n{removed}",
            title="[status.success]Clean Complete[/status.success]",
            box=ROUNDED,
            border_style="success",
            padding=(1, 2),
        )
    )
    return 0


def _render_not_installed(error: Exception) -> None:
    installed = getattr(error, "installed", None) or getattr(error, "matches", [])
    tool = getattr(error, "tool", "")
    if installed:
        listing = "\n".join(f"  • {v}" for v in installed)
        suggestion = (
            f"Currently installed versions of '{tool}':\n{listing}\n\n"
            f"Re-run with one of these, e.g.:\nshelley clean {tool}:{installed[0]}"
        )
    else:
        suggestion = f"'{tool}' has no installed versions to clean."
    console.print(
        ShelleyStyle.create_error_panel("Not Installed", str(error), suggestion)
    )


def _confirm(tool: str, tag: str) -> bool:
    try:
        return bool(
            questionary.confirm(
                f"Remove {tool}/{tag}? This deletes its module, wrappers, "
                "and container artifacts.",
                default=False,
            ).ask()
        )
    except (EOFError, OSError):  # no terminal to ask on
        return False


def _split_resolved(argv: list[str]) -> tuple[str | None, list[str]]:
    resolved, positional = None, []
    it = iter(argv)
    for arg in it:
        if arg == RESOLVED_FLAG:
            resolved = next(it, "")
        elif arg.startswith(RESOLVED_FLAG + "="):
            resolved = arg.split("=", 1)[1]
        else:
            positional.append(arg)
    return resolved, positional
