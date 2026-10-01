"""Tests for how the build path re-invokes itself under sudo.

Two bugs are guarded here:

1. The launcher path was once derived from __file__, assuming a `bin/shelley` sibling of
   the package. False under a `uv tool install` layout, where the launcher lives in
   .../uv/tools/shelley/bin/ while the package lives in .../site-packages/shelley/.
   resolve_shelley_executable resolves via PATH instead.
2. A PATH lookup can resolve to a *different installation* than the one running. With a
   system-wide shelley present, `uv run shelley build` in a checkout re-exec'd the system
   copy, so the privileged half of the build ran older code — silently installing to the
   wrong place while the unprivileged half printed the new version's output.
   reexec_command re-runs the current package via `sys.executable -m shelley`.
"""

import os
import subprocess
import sys

from shelley.commands.build import reexec_command, resolve_shelley_executable


def _make_executable(path):
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)


def test_finds_launcher_on_path(tmp_path, monkeypatch):
    """When a `shelley` executable is on PATH, it is returned as-is."""
    launcher = tmp_path / "shelley"
    _make_executable(launcher)
    monkeypatch.setenv("PATH", str(tmp_path))

    assert resolve_shelley_executable() == str(launcher)


def test_returns_none_when_absent(tmp_path, monkeypatch):
    """With no `shelley` anywhere on PATH, resolution fails cleanly (None)."""
    empty = tmp_path / "empty_bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert resolve_shelley_executable() is None


def test_path_independent_of_package_location(tmp_path, monkeypatch):
    """The launcher is found via PATH even though it is nowhere near the package.

    This mirrors the uv-tool layout that broke the old __file__-derived logic:
    the launcher sits in an isolated bin/ dir unrelated to site-packages.
    """
    tool_bin = tmp_path / "uv" / "tools" / "shelley" / "bin"
    tool_bin.mkdir(parents=True)
    launcher = tool_bin / "shelley"
    _make_executable(launcher)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tool_bin), "/usr/bin"]))

    assert resolve_shelley_executable() == str(launcher)


# ---------------------------------------------------------------------------
# reexec_command — must re-run *this* shelley, not whatever is on PATH
# ---------------------------------------------------------------------------


def test_reexec_uses_the_running_interpreter():
    assert reexec_command() == [sys.executable, "-m", "shelley"]


def test_reexec_ignores_a_different_shelley_on_path(tmp_path, monkeypatch):
    """A system-wide install must not hijack the privileged half of the build."""
    other = tmp_path / "other-install" / "bin"
    other.mkdir(parents=True)
    _make_executable(other / "shelley")
    monkeypatch.setenv("PATH", str(other))

    cmd = reexec_command()

    assert cmd == [sys.executable, "-m", "shelley"]
    assert str(other) not in " ".join(cmd)


def test_reexec_falls_back_to_path_when_package_is_unimportable(tmp_path, monkeypatch):
    launcher = tmp_path / "shelley"
    _make_executable(launcher)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(
        "shelley.commands.build.importlib.util.find_spec", lambda name: None
    )

    assert reexec_command() == [str(launcher)]


def test_python_m_shelley_is_actually_runnable():
    """`-m shelley` needs shelley/__main__.py; without it the re-exec would fail."""
    result = subprocess.run(
        [sys.executable, "-m", "shelley", "--version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "helley" in result.stdout
