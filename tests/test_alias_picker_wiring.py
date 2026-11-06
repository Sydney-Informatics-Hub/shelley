"""How `build -i` reaches the alias picker: facade, mouse switch, no-terminal error, root re-exec."""

import subprocess
import sys
from pathlib import Path

import pytest

from shelley import ui
from shelley.builder import guts_integration
from shelley.client import build
from shelley.results import Resolved
from shelley.tags import Tag
from shelley.ui.alias_picker import PickedAlias
from shelley.utils.style import console

# ---- mouse switch and terminal check ---------------------------------------------------------------


def test_mouse_on_by_default(monkeypatch):
    monkeypatch.delenv("SHELLEY_MOUSE", raising=False)
    assert ui.mouse_enabled() is True


def test_no_mouse_flag(monkeypatch):
    monkeypatch.delenv("SHELLEY_MOUSE", raising=False)
    assert ui.mouse_enabled(no_mouse_flag=True) is False


@pytest.mark.parametrize(
    ("value", "expected"), [("0", False), (" 0 ", False), ("1", True), ("", True)]
)
def test_shelley_mouse_env(monkeypatch, value, expected):
    monkeypatch.setenv("SHELLEY_MOUSE", value)
    assert ui.mouse_enabled() is expected


@pytest.mark.parametrize(
    ("stdin", "stderr", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_interactive_terminal(monkeypatch, stdin, stderr, expected):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: stdin)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: stderr)
    assert ui.interactive_terminal() is expected


def test_textual_stays_off_the_cli_import_path():
    code = "import sys, shelley.client.cli; print('textual' in sys.modules)"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


# ---- edit_aliases_interactive ------------------------------------------------------------------------


def test_edit_aliases_interactive_returns_ticked_names(monkeypatch):
    seen = {}

    def fake_picker(aliases, container, version, *, mouse):
        seen.update(aliases=aliases, container=container, version=version, mouse=mouse)
        return [PickedAlias("sam2vcf", "/usr/local/bin/sam2vcf.pl", "sam2vcf.pl")]

    monkeypatch.setattr(guts_integration, "alias_picker", fake_picker)
    result = guts_integration.edit_aliases_interactive(
        [{"sam2vcf.pl": "/usr/local/bin/sam2vcf.pl"}], "samtools", "1.21", mouse=False
    )
    assert result == [{"name": "sam2vcf", "command": "/usr/local/bin/sam2vcf.pl"}]
    assert seen == {
        "aliases": [{"name": "sam2vcf.pl", "command": "/usr/local/bin/sam2vcf.pl"}],
        "container": "samtools",
        "version": "1.21",
        "mouse": False,
    }


def test_edit_aliases_interactive_cancel_raises(monkeypatch):
    monkeypatch.setattr(guts_integration, "alias_picker", lambda *a, **k: None)
    with pytest.raises(ValueError):
        guts_integration.edit_aliases_interactive([], "samtools", "1.21")


# ---- build -i ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["samtools", "-i"], (True, False, [], ["samtools"])),
        (["samtools", "-i", "--no-mouse"], (True, True, [], ["samtools"])),
        (["--no-mouse", "samtools"], (False, True, [], ["samtools"])),
    ],
)
def test_parse_no_mouse(argv, expected):
    assert build._parse(argv) == expected


def test_build_i_without_terminal_says_so(monkeypatch):
    monkeypatch.setattr(build, "interactive_terminal", lambda: False)
    with console.capture() as captured:
        code = build.run(["samtools/1.21", "-i"])
    out = captured.get()
    assert code == 1
    assert "× Error: -i/--interactive needs an interactive terminal." in out
    assert "To build without choosing aliases:  shelley build samtools/1.21" in out


def test_root_reexec_keeps_no_mouse(monkeypatch):
    item = Resolved(
        "samtools/1.21", "samtools", Tag("1.21--h50ea8bc_0"), Path("/x.sif")
    )
    monkeypatch.setattr(build, "interactive_terminal", lambda: True)
    monkeypatch.setattr(build.services, "resolve_all", lambda *a, **k: ([item], []))
    monkeypatch.setattr(build.privilege, "needs_root", lambda: True)
    seen = {}
    monkeypatch.setattr(
        build.privilege, "reexec", lambda args: seen.setdefault("args", args) and 0
    )
    with console.capture():
        build.run(["samtools/1.21", "-i", "--no-mouse"])
    assert seen["args"][-2:] == ["--interactive", "--no-mouse"]


def test_build_passes_tool_and_version_to_the_picker(monkeypatch):
    item = Resolved(
        "samtools/1.21", "samtools", Tag("1.21--h50ea8bc_0"), Path("/x.sif")
    )
    calls = []

    def fake_build_resolved(items, exposer, curate=None):
        calls.append(curate)
        return []

    monkeypatch.setattr(build.services, "prepare_build_environment", lambda *_: None)
    monkeypatch.setattr(build.services, "build_resolved", fake_build_resolved)
    monkeypatch.setattr(
        build, "Lmod", lambda: type("L", (), {"load_build_modules": None})()
    )
    monkeypatch.setattr(build, "ShpcExposer", lambda lmod: object())
    build._apply_and_render([item], interactive=True, batch=False, mouse=False)
    (curate,) = calls
    assert curate.keywords == {
        "container": "samtools",
        "version": "1.21--h50ea8bc_0",
        "mouse": False,
    }
