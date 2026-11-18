#!/usr/bin/env python3
"""
Shelley Styling Module

Rich-based styling for Shelley following Australian BioCommons design guidelines.
Provides consistent colors, themes, and output formatting across the application.

Rules (docs/reference/style-guide.md): hex values live here, callers use
role names ("error", "version", "command"), Rich output never sets a text colour.
"""

from pathlib import Path
from typing import Any

from rich.align import Align
from rich.box import DOUBLE, ROUNDED, SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Australian BioCommons Color Palette (Official Colors)
BIOCOMMONS_COLORS = {
    # Primary BioCommons brand colors
    "primary": "#2cb77c",  # PANTONE 2413 - Bright Green (primary brand)
    "secondary": "#205a86",  # PANTONE 2161 - Dark Blue (selection fill only, not text)
    "accent": "#f49f1d",  # PANTONE 7408 - Orange
    # BioCommons logo colors
    "magenta": "#ed087c",  # PANTONE 226 - Bright Pink/Magenta
    "teal": "#5ac3b1",  # PANTONE 7465 - Teal/Turquoise
    "purple": "#b21e8d",  # PANTONE 241 - Purple/Magenta (not for text: fails contrast)
    "sage": "#8ea869",  # PANTONE 5777 - Sage Green
    # Status colors (adapted from BioCommons palette)
    "success": "#2cb77c",  # Bright Green
    "warning": "#f49f1d",  # Orange
    "error": "#f35eaa",  # Bright Pink, lightened 35% for 4.5:1 contrast
    "info": "#5ac3b1",  # Teal
    # UI colors (no text colour: body text uses the terminal's own foreground)
    "muted": "#8a96a3",  # Slate Gray, lightened - muted text
    "border": "#2cb77c",  # Bright Green - panel and table borders
    # Tool colors
    "tool": "#2cb77c",  # Bright Green - tool names
    "version": "#799cb6",  # Dark Blue, lightened 40% - version numbers
    "command": "#8ea869",  # Sage Green - commands
    "path": "#5ac3b1",  # Teal - file paths
    # Textual widget grounds (not used for Rich output)
    "background": "#1c1d20",  # typical dark terminal background
    "surface": "#2a2c31",  # raised surface: list rows, key bar
    "panel": "#33363c",  # title bars, column headings
    "foreground": "#e6e6e6",  # widget text
    "cancel": "#3a3d44",  # neutral Cancel button fill
    "on_selection": "#ffffff",  # text on the secondary (selection) fill
}

# Roles that must never be used as text on the Textual panel colour (below 4.5:1 there).
NOT_ON_PANEL = ("error", "version", "muted")

# Rich Theme Definition
SHELLEY_THEME = Theme(
    {
        # Basic styling
        "primary": BIOCOMMONS_COLORS["primary"],
        "success": BIOCOMMONS_COLORS["success"],
        "warning": BIOCOMMONS_COLORS["warning"],
        "error": BIOCOMMONS_COLORS["error"],
        "info": BIOCOMMONS_COLORS["info"],
        "muted": BIOCOMMONS_COLORS["muted"],
        # Semantic styling
        "version": BIOCOMMONS_COLORS["version"],
        "command": BIOCOMMONS_COLORS["command"],
        "path": BIOCOMMONS_COLORS["path"],
        # Status styling
        "status.success": f"bold {BIOCOMMONS_COLORS['success']}",
        "status.warning": f"bold {BIOCOMMONS_COLORS['warning']}",
        "status.error": f"bold {BIOCOMMONS_COLORS['error']}",
        "status.info": f"bold {BIOCOMMONS_COLORS['info']}",
        # UI elements
        "heading": f"bold {BIOCOMMONS_COLORS['primary']}",
        "label": f"bold {BIOCOMMONS_COLORS['primary']}",
        "prompt": f"bold {BIOCOMMONS_COLORS['primary']}",
        "border": BIOCOMMONS_COLORS["border"],
        "hint": BIOCOMMONS_COLORS["muted"],
        "hint.command": f"bold {BIOCOMMONS_COLORS['command']}",
        "yes": f"bold {BIOCOMMONS_COLORS['primary']}",
        "no": BIOCOMMONS_COLORS["muted"],
        # Progress bars
        "progress.remaining": BIOCOMMONS_COLORS["muted"],
    }
)

# Symbols to ensure interoperability (WGL4 with exceptions). No emojis as it inconsistently break rendering for borders
STATUS = {
    # kind: (symbol, word)
    "success": ("√", "Done:"),
    "info": ("i", "Note:"),
    "warning": ("!", "Warning:"),
    "error": ("×", "Error:"),  # U+00D7 multiplication sign, not the letter x
}
SPINNER = "dots"  # braille, not WGL4: kept by choice; the words carry the meaning
TICK_ON, TICK_OFF = "[x]", "[ ]"
POINTER = "›"
FOCUS_LEFT, FOCUS_RIGHT = "›", "‹"  # focused button: "› Confirm ‹"
MORE_ABOVE, MORE_BELOW = "▲", "▼"
SEP = " · "
ELLIPSIS = "…"
YES, NO = "yes", "no"

# Banned in any output (tests scan the source tree for these). May not be supported across all terminals and systems
BANNED_CHARS = "✓✔✗✘⚠ℹ"
BANNED_RANGES = [
    (0x1F300, 0x1FAFF),  # emoji blocks
    (0xFE0F, 0xFE0F),  # emoji variation selector
]


def status_markup(kind: str, message: str) -> str:
    """One status line head + message, e.g. status_markup("error", 'No tool matches "x".')."""
    symbol, word = STATUS[kind]
    return f"[status.{kind}]{symbol} {word}[/] {message}"


def make_textual_theme():
    """Return the BioCommons Textual theme, built from BIOCOMMONS_COLORS.

    Register it in the App's __init__, not on_mount (the app's CSS is parsed before mount,
    so variables such as $shelley-cancel would be undefined), and run the App with
    ansi_color=False, otherwise Textual ignores these values and uses the terminal palette.
    Textual is imported lazily to keep it off the CLI's import path.
    """
    from textual.theme import Theme as TextualTheme

    c = BIOCOMMONS_COLORS
    return TextualTheme(
        name="biocommons",
        primary=c["primary"],
        secondary=c["secondary"],  # selection fill
        accent=c["warning"],  # reserved for warnings in dialogs
        foreground=c["foreground"],
        background=c["background"],
        surface=c["surface"],
        panel=c["panel"],
        success=c["success"],
        warning=c["warning"],
        error=c["error"],
        dark=True,
        variables={
            # usable in TCSS as $shelley-cancel etc.
            "shelley-cancel": c["cancel"],
            "shelley-muted": c["muted"],
            "shelley-on-primary": c["background"],  # dark text on green buttons
            "shelley-on-selection": c["on_selection"],
        },
    )


# Global console instance with BioCommons theme
console = Console(theme=SHELLEY_THEME, width=120)

# Banner artwork, shared with the BioShell login banner (/etc/update-motd.d).
# Every line is exactly BANNER_WIDTH cells wide; `{welcome}` is filled with the
# inner content (BANNER_WIDTH - 2 cells) by create_banner().
BANNER_WIDTH = 87
BANNER_ART = """\
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                       ☆                              ★  ☆           │
│                               ★                  ★                   ☆              │
│       ☆         ☆                                                                   │
│★           ★                                  ☆               ★                     │
│            ☆                    ★                                                   │
│                                                                    ★                │
│            ████  ▒▒▒                                                      ☆         │
│           ██████ ▒▘▒▒                          ★                                    │
│        ▒▒████████▒▒                                                                 │
│───────── ▒▒    ▒▒ ──────────────────────────────────────────────────────────────────│
│                                                                                     │
│{welcome}│
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘"""


class ShelleyStyle:
    """Styling utilities for Shelley."""

    @staticmethod
    def create_header(title: str, subtitle: str = "") -> Panel:
        """Create a styled header panel."""
        if subtitle:
            content = f"[heading]{title}[/heading]\n[muted]{subtitle}[/muted]"
        else:
            content = f"[heading]{title}[/heading]"

        return Panel(
            Align.center(content), box=DOUBLE, border_style="primary", padding=(1, 2)
        )

    @staticmethod
    def create_banner() -> Text:
        """Create the main Shelley banner (shares the BioShell MOTD artwork).

        The artwork draws its own frame, so it is returned as plain Text rather
        than wrapped in a Panel. Keep it in sync with the login banner at
        build/ansible/roles/motd/files/99-bioshell in the BioShell repo.
        """
        from .. import __version__

        left = "   Hey there, I'm Shelley!"
        right = f"v{__version__}   "
        pad = " " * max(1, BANNER_WIDTH - 2 - len(left) - len(right))
        welcome = f"{left}{pad}{right}"

        return Text.from_markup(
            f"[bold][info]{BANNER_ART.format(welcome=welcome)}[/info][/bold]"
        )

    @staticmethod
    def create_help_table(commands: list[dict[str, str]]) -> Table:
        """Create a styled help table."""
        table = Table(
            title="[primary][bold]Available Commands[/bold][/primary]",
            box=ROUNDED,
            border_style="primary",
            header_style="heading",
            show_lines=True,
        )

        table.add_column("Command", style="primary", no_wrap=True)
        table.add_column("Description", style="muted")
        table.add_column("Example", style="primary")

        for cmd in commands:
            table.add_row(cmd["command"], cmd["description"], cmd.get("example", ""))

        return table

    @staticmethod
    def create_versions_table(tool_name: str, versions: list[str]) -> Table:
        """Create a styled versions table."""
        table = Table(
            title=f"[primary][bold]Available Versions for[/bold][/primary] [primary][bold]{tool_name}[/bold][/primary]",
            box=ROUNDED,
            border_style="primary",
            header_style="heading",
            show_header=False,
        )

        table.add_column("Version", style="primary")
        table.add_column("Status", style="success")

        for version in versions:
            table.add_row(version, "✓ Available")

        return table

    @staticmethod
    def create_versions_with_paths_table(
        tool_name: str, version_path_pairs: list[tuple[str, str]]
    ) -> Table:
        """Create a styled versions table with full CVMFS paths."""
        table = Table(
            title=f"[primary][bold]Available Versions for[/bold][/primary] [primary][bold]{tool_name}[/bold][/primary]",
            box=ROUNDED,
            border_style="primary",
            header_style="heading",
            show_header=False,
        )

        table.add_column("Version", style="primary", no_wrap=True)
        table.add_column("Container Path", style="path")

        for version, path in version_path_pairs:
            table.add_row(version, path)

        return table

    @staticmethod
    def create_tools_table(tools: list[dict[str, Any]], limit: int = None) -> Table:
        """Create a styled tools list table."""
        display_count = len(tools)
        if limit and len(tools) > limit:
            tools = tools[:limit]

        table = Table(
            title=f"[heading]Bioinformatics Tools[/heading] [muted]({len(tools)} shown{f' of {display_count}' if limit else ''})[/muted]",
            box=ROUNDED,
            border_style="border",
            header_style="heading",
        )

        table.add_column("Tool", style="primary", no_wrap=True)
        table.add_column("Description", style="muted", ratio=2)
        table.add_column("Category", style="info")

        for tool in tools:
            table.add_row(
                tool.get("name", "Unknown"),
                tool.get("description", "No description available")[:80] + "..."
                if tool.get("description", "") and len(tool.get("description", "")) > 80
                else tool.get("description", "No description available"),
                tool.get("category", "General"),
            )

        return table

    @staticmethod
    def create_build_success(tool_name: str, version: str, module_path: Path) -> Panel:
        """Create a styled build success message."""
        content = f"""[status.success]✅ Module Built Successfully![/status.success]

[label]Tool:[/label] [primary]{tool_name}[/primary]
[label]Version:[/label] [version]{version}[/version]
[label]Module Path:[/label] [path]{module_path}[/path]

[label]To load this module:[/label]
[command]module load {tool_name}/{version}[/command]

[label]To list all modules:[/label]
[command]module avail[/command]"""

        return Panel(
            content,
            title="[status.success]Build Complete[/status.success]",
            box=ROUNDED,
            border_style="success",
            padding=(1, 2),
        )

    @staticmethod
    def create_build_info(
        tool_name: str, version: str, available_versions: list[str]
    ) -> Panel:
        """Create build information panel for version selection."""
        versions_text = "\n".join(
            [f"  [version]• {v}[/version]" for v in available_versions[:10]]
        )
        if len(available_versions) > 10:
            versions_text += (
                f"\n  [muted]... and {len(available_versions) - 10} more[/muted]"
            )

        content = f"""[status.info]ℹ️  Version Selection[/status.info]

[label]Available versions for[/label] [primary]{tool_name}[/primary]:
{versions_text}

[status.warning]⚠️  No version specified[/status.warning]
[label]Building latest version:[/label] [version]{version}[/version]

[label]To specify a version:[/label]
[command]shelley build {tool_name}/{version}[/command]"""

        return Panel(
            content,
            title="[status.info]Version Information[/status.info]",
            box=ROUNDED,
            border_style="info",
            padding=(1, 2),
        )

    @staticmethod
    def create_error_panel(title: str, message: str, suggestion: str = "") -> Panel:
        """Create a styled error panel."""
        content = f"[status.error]❌ {message}[/status.error]"
        if suggestion:
            content += f"\n\n[label]Suggestion:[/label]\n[info]{suggestion}[/info]"

        return Panel(
            content,
            title=f"[status.error]{title}[/status.error]",
            box=ROUNDED,
            border_style="error",
            padding=(1, 2),
        )

    @staticmethod
    def create_warning_panel(title: str, message: str) -> Panel:
        """Create a styled warning panel."""
        return Panel(
            f"[status.warning]⚠️  {message}[/status.warning]",
            title=f"[status.warning]{title}[/status.warning]",
            box=ROUNDED,
            border_style="warning",
            padding=(1, 2),
        )

    @staticmethod
    def create_info_panel(title: str, message: str) -> Panel:
        """Create a styled info panel."""
        return Panel(
            f"[status.info]ℹ️  {message}[/status.info]",
            title=f"[status.info]{title}[/status.info]",
            box=ROUNDED,
            border_style="info",
            padding=(1, 2),
        )

    @staticmethod
    def format_command_examples() -> Table:
        """Create a table of command examples."""
        table = Table(
            title="[heading]Command Examples[/heading]",
            box=SIMPLE,
            border_style="border",
            header_style="heading",
        )

        table.add_column("Use Case", style="muted", ratio=1)
        table.add_column("Command", style="command", ratio=2)

        examples = [
            ("Find a specific tool", "shelley find fastqc"),
            ("List available versions", "shelley find fastqc -v"),
            ("Search by functionality", "shelley search 'quality control'"),
            ("Search for RNA-seq tools", "shelley search 'RNA sequencing'"),
            ("Build latest version", "shelley build samtools"),
            ("Build specific version", "shelley build samtools/1.21"),
            ("Uninstall a tool version", "shelley clean samtools:1.21"),
            ("Uninstall without confirming", "shelley clean samtools:1.21 -y"),
            ("Interactive mode", "shelley interactive"),
        ]

        for use_case, command in examples:
            table.add_row(use_case, command)

        return table

    @staticmethod
    def create_version_info() -> str:
        """Get version information for display."""
        # Single source of truth: shelley/__init__.py:__version__ (pyproject
        # derives the package version from it). Reading it directly is correct
        # whether shelley is pip-installed or run from a source checkout.
        from .. import __version__

        return f"[heading]Shelley[/heading] [version]{__version__}[/version]"

    @staticmethod
    def create_progress_bar(description: str) -> Progress:
        """Create a styled progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None, style="primary", complete_style="success"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        )

    @staticmethod
    def create_status_summary(
        success: int, total: int, operation: str = "operation"
    ) -> Panel:
        """Create a standardized status summary panel."""
        if success == total:
            title = f"[status.success]All {operation}s Completed Successfully![/status.success]"
            style = "success"
            icon = "🎉"
        elif success > 0:
            title = "[status.warning]Partial Success[/status.warning]"
            style = "warning"
            icon = "⚠️"
        else:
            title = f"[status.error]All {operation}s Failed[/status.error]"
            style = "error"
            icon = "❌"

        content = f"{icon} [label]Successfully completed:[/label] [label]{success}/{total}[/label] {operation}s"

        return Panel(
            content, title=title, box=ROUNDED, border_style=style, padding=(1, 2)
        )

    @staticmethod
    def create_status(message: str) -> Status:
        """Create a styled status indicator."""
        return Status(
            message, spinner=SPINNER, spinner_style="primary", console=console
        )


# Convenience functions for common operations
def print_banner():
    """Print the main Shelley banner."""
    console.print(ShelleyStyle.create_banner())


def print_header(title: str, subtitle: str = ""):
    """Print a styled header."""
    console.print(ShelleyStyle.create_header(title, subtitle))


def print_success(message: str):
    """Print a success message."""
    console.print(f"[status.success]✓ {message}[/status.success]")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[status.warning]⚠️  {message}[/status.warning]")


def print_error(message: str):
    """Print an error message."""
    console.print(f"[status.error]❌ {message}[/status.error]")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[status.info]ℹ️  {message}[/status.info]")


def print_rule(title: str = "", style: str = "primary"):
    """Print a styled horizontal rule."""
    console.rule(title, style=style)


def print_command(command: str):
    """Print a command in the styled format."""
    console.print(f"[command]{command}[/command]")


def print_version():
    """Print version information, plus an upgrade notice if main is ahead."""
    console.print(ShelleyStyle.create_version_info())
    print_update_notice()


def print_update_notice():
    """Print a notice if a newer shelley is available on main (silent otherwise)."""
    from .update_check import check_for_update, format_update_notice

    latest = check_for_update()
    if latest:
        console.print(
            Panel(
                format_update_notice(latest),
                title="[status.warning]⬆️  Update available[/status.warning]",
                box=ROUNDED,
                border_style="warning",
                padding=(1, 2),
            )
        )
