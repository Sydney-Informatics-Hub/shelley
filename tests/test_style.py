"""Guard tests for the terminal style guide (docs/reference/style-guide.md).

The source scans use a ratchet: files that already broke a rule when the test was added are listed in
KNOWN_*_OFFENDERS. A file not on the list must follow the rule. A listed file that has been fixed must be
removed from the list, so the list only ever shrinks.
"""

import ast
import re
from pathlib import Path

import pytest
from rich.default_styles import DEFAULT_STYLES
from rich.markup import RE_TAGS

from shelley.utils import style
from shelley.utils.style import (
    BANNED_CHARS,
    BANNED_RANGES,
    BIOCOMMONS_COLORS,
    NOT_ON_PANEL,
    SHELLEY_THEME,
    console,
)

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "shelley"
STYLE_PY = PACKAGE / "utils" / "style.py"

SOURCES = sorted(
    p
    for p in PACKAGE.rglob("*")
    if p.suffix in {".py", ".tcss"}
    and "_vendor" not in p.parts
    and "test" not in p.name
)
PYTHON_SOURCES = [p for p in SOURCES if p.suffix == ".py"]
DOCS = sorted([*(REPO / "docs").rglob("*.md"), REPO / "README.md"])

HEX = re.compile(r"#[0-9a-fA-F]{6}\b")

# Ratchet: files that broke a rule when this test was added. Remove entries as files are fixed.
KNOWN_HEX_OFFENDERS: set[str] = set()
KNOWN_GLYPH_OFFENDERS = {
    "shelley/client/build.py",
    "shelley/client/discovery.py",
    "shelley/scripts/assess_regression_tools.py",
    "shelley/utils/constants.py",  # keycap emoji in comments
    "shelley/utils/style.py",
}

# Colours used as text, which must reach 4.5:1 on the terminal background and the Textual surface.
TEXT_ROLES = (
    "primary",
    "success",
    "info",
    "path",
    "warning",
    "error",
    "version",
    "command",
    "muted",
)
MIN_CONTRAST = 4.5


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def string_literals(path: Path):
    """Yield (line, text) for every string literal in a Python file."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def banned_in(path: Path) -> list[str]:
    """Banned characters anywhere in a file, except style.py's own BANNED_CHARS definition."""
    return sorted(
        {
            ch
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("BANNED_CHARS")
            for ch in line
            if is_banned(ch)
        }
    )


def is_banned(ch: str) -> bool:
    return ch in BANNED_CHARS or any(lo <= ord(ch) <= hi for lo, hi in BANNED_RANGES)


def contrast(fg: str, bg: str) -> float:
    """WCAG 2 contrast ratio between two #rrggbb colours."""

    def luminance(hex_colour: str) -> float:
        channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# --------------------------------------------------------------------------------------------------------------
# Source scans (ratcheted)
# --------------------------------------------------------------------------------------------------------------


def test_no_hex_outside_style_py():
    offenders = {
        rel(p)
        for p in SOURCES
        if p != STYLE_PY and HEX.search(p.read_text(encoding="utf-8"))
    }
    assert offenders <= KNOWN_HEX_OFFENDERS, (
        f"Hex colours outside style.py: {sorted(offenders - KNOWN_HEX_OFFENDERS)}. "
        "Use a role name from style.py instead."
    )
    fixed = KNOWN_HEX_OFFENDERS - offenders
    assert not fixed, f"Fixed, remove from KNOWN_HEX_OFFENDERS: {sorted(fixed)}"


def test_no_hex_in_docs():
    offenders = [rel(p) for p in DOCS if HEX.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"Hex colours in docs (name the role instead): {offenders}"


def test_no_banned_glyphs():
    offenders = {rel(p): banned_in(p) for p in SOURCES}
    offenders = {k: v for k, v in offenders.items() if v}
    new = {k: v for k, v in offenders.items() if k not in KNOWN_GLYPH_OFFENDERS}
    assert not new, (
        f"Banned symbols or emoji: {new}. "
        "Use the WGL4 symbols in style.py (STATUS, YES/NO, TICK_ON/TICK_OFF)."
    )
    fixed = KNOWN_GLYPH_OFFENDERS - offenders.keys()
    assert not fixed, f"Fixed, remove from KNOWN_GLYPH_OFFENDERS: {sorted(fixed)}"


@pytest.mark.parametrize("path", PYTHON_SOURCES, ids=rel)
def test_markup_tags_resolve(path):
    """Every opening tag in a markup string must be a theme style or a valid Rich style.

    Catches tags Rich silently drops, such as "[bold info]": a theme name can't be combined with other
    attributes in one tag. Nest them instead: "[bold][info]…[/info][/bold]". Only strings containing
    a closing tag are checked, to skip usage text such as "[options]".
    """
    bad = []
    for line, text in string_literals(path):
        if "[/" not in text:
            continue
        for match in RE_TAGS.finditer(text):
            escapes, tag = match.group(2), match.group(3)
            if escapes or tag.startswith(("/", "@", "link")):
                continue
            try:
                console.get_style(tag)
            except Exception:
                bad.append((line, tag))
    assert not bad, f"Unknown Rich styles (silently unstyled): {bad}"


# --------------------------------------------------------------------------------------------------------------
# Colour values
# --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", TEXT_ROLES)
@pytest.mark.parametrize("ground", ["background", "surface"])
def test_text_roles_reach_contrast(role, ground):
    ratio = contrast(BIOCOMMONS_COLORS[role], BIOCOMMONS_COLORS[ground])
    assert ratio >= MIN_CONTRAST, f"{role} on {ground}: {ratio:.2f}:1"


def test_not_on_panel_list_is_accurate():
    """Roles listed as unsafe on the panel colour really are below 4.5:1 there, and no others are."""
    panel = BIOCOMMONS_COLORS["panel"]
    below = {
        r for r in TEXT_ROLES if contrast(BIOCOMMONS_COLORS[r], panel) < MIN_CONTRAST
    }
    assert below == set(NOT_ON_PANEL)


@pytest.mark.parametrize(
    ("fg", "bg"),
    [
        ("foreground", "background"),
        ("foreground", "surface"),
        ("foreground", "panel"),
        ("foreground", "cancel"),  # Cancel button text
        ("on_selection", "secondary"),  # highlighted row
        ("background", "primary"),  # Confirm button: dark text on green
        ("background", "warning"),  # Discard and exit button: dark text on orange
    ],
)
def test_widget_pairs_reach_contrast(fg, bg):
    ratio = contrast(BIOCOMMONS_COLORS[fg], BIOCOMMONS_COLORS[bg])
    assert ratio >= MIN_CONTRAST, f"{fg} on {bg}: {ratio:.2f}:1"


def test_theme_roles_match_palette():
    for role in TEXT_ROLES:
        theme_colour = SHELLEY_THEME.styles[role].color
        assert theme_colour is not None, role
        assert theme_colour.triplet.hex == BIOCOMMONS_COLORS[role], role


def test_rich_theme_sets_no_text_colour_or_background():
    """Body text uses the terminal's own foreground: no theme style may paint a ground or fixed text."""
    fixed = {
        BIOCOMMONS_COLORS[k]
        for k in ("background", "surface", "panel", "foreground", "on_selection")
    } | {"#000000"}
    for name, rich_style in SHELLEY_THEME.styles.items():
        if DEFAULT_STYLES.get(name) == rich_style:
            continue  # Rich's own default, inherited by the theme
        assert rich_style.bgcolor is None, f"{name} sets a background"
        if rich_style.color is not None and rich_style.color.triplet is not None:
            assert rich_style.color.triplet.hex not in fixed, (
                f"{name} sets a fixed text colour"
            )


# --------------------------------------------------------------------------------------------------------------
# Symbols and helpers
# --------------------------------------------------------------------------------------------------------------


def test_status_symbols_are_allowed():
    for kind, (symbol, word) in style.STATUS.items():
        assert not any(is_banned(ch) for ch in symbol), kind
        assert word.endswith(":"), kind
    assert style.STATUS["error"][0] == "×"  # multiplication sign, not the letter x


def test_status_markup_renders_role_colour():
    with console.capture() as capture:
        console.print(style.status_markup("error", "Boom."), highlight=False)
    assert capture.get().strip() == "× Error: Boom."
    for kind in style.STATUS:
        assert console.get_style(f"status.{kind}").bold


# --------------------------------------------------------------------------------------------------------------
# Textual theme
# --------------------------------------------------------------------------------------------------------------


def test_style_py_does_not_import_textual_at_module_level():
    tree = ast.parse(STYLE_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert not any(n.split(".")[0] == "textual" for n in names), names


def test_textual_theme_builds():
    theme = style.make_textual_theme()
    assert theme.name == "biocommons"
    assert theme.dark
    assert theme.primary == BIOCOMMONS_COLORS["primary"]
    assert theme.secondary == BIOCOMMONS_COLORS["secondary"]
    assert theme.accent == BIOCOMMONS_COLORS["warning"]
    for variable in (
        "shelley-cancel",
        "shelley-muted",
        "shelley-on-primary",
        "shelley-on-selection",
    ):
        assert variable in theme.variables
