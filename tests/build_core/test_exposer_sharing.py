"""A build must be usable by every user on the VM (ported from the 0.4.0 builder tests).

See ``docs/explanation/build-design.md``: shpc is pinned to the shared settings file,
artefacts stay root-owned and are hardened per tool, never chowned to the builder.
"""

import os
import shutil
import stat
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import shelley.galaxy.exposer as exposer_mod
import shelley.tools.shpc as shpc_mod
from shelley.tags import Tag
from shelley.tools.shpc import Shpc
from shelley.utils import globals as gl

from .fakes import FakeShpc
from .test_exposer import UP, URI, build, make


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def sif(tmp_path):
    path = tmp_path / "samtools.sif"
    path.touch()
    return path


# ------------------------------------------------------------------ settings file
@pytest.fixture
def shpc_runs(monkeypatch):
    calls: list[list[str]] = []

    def run(argv, **_):
        calls.append(argv)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shpc_mod.subprocess, "run", run)
    return calls


def test_every_shpc_call_pins_the_shared_settings_file(shpc_runs, tmp_path):
    settings = gl.shpc_settings_file()
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("module_base: /apps/shpc/modules\n")
    shpc = Shpc(binary="shpc")
    shpc.install(f"{URI}:{UP.raw}", tmp_path / "x.sif")
    shpc.uninstall(f"{URI}:{UP.raw}")
    shpc.module_base()
    assert len(shpc_runs) == 3
    for argv in shpc_runs:
        assert argv[1:3] == ["--settings-file", str(settings)], argv


def test_shpc_omits_the_flag_when_the_settings_file_is_absent(
    shpc_runs, tmp_path, monkeypatch
):
    """shpc hard-exits on a missing --settings-file."""
    monkeypatch.setattr(gl, "shpc_settings_file", lambda: tmp_path / "absent.yml")
    Shpc(binary="shpc").module_base()
    assert "--settings-file" not in shpc_runs[0]


def test_module_base_falls_back_when_shpc_cannot_report_it(monkeypatch):
    monkeypatch.setattr(
        shpc_mod.subprocess,
        "run",
        lambda argv, **_: MagicMock(returncode=1, stdout="", stderr="boom"),
    )
    assert Shpc(binary="shpc").module_base() == gl.shpc_module_base()


# ------------------------------------------------------------------ permissions
class StrictUmaskShpc(FakeShpc):
    """Writes what shpc writes under a ``umask 077``: nothing readable by others."""

    def install(self, uri_tag, sif):
        super().install(uri_tag, sif)
        uri, tag = uri_tag.rsplit(":", 1)
        module_dir = gl.shpc_module_base() / uri / tag
        os.chmod(module_dir / "module.lua", 0o600)
        os.chmod(gl.shpc_module_base() / uri / ".version", 0o600)
        os.chmod(module_dir, 0o700)
        tool = uri.rsplit("/", 1)[1]
        os.chmod(gl.shpc_wrapper_base() / uri / tag / "bin" / tool, 0o700)


def test_build_never_chowns(sif, monkeypatch):
    """Handing the tree to $SUDO_USER is what made 0.4.0's first builds single-user."""
    monkeypatch.setenv("SUDO_USER", "ubuntu")
    for target in (os, shutil):
        monkeypatch.setattr(
            target, "chown", lambda *a, **k: pytest.fail("chown called"), raising=False
        )
    build(make(), UP, sif)


def test_build_hardens_this_tools_dirs_only(sif, monkeypatch):
    """Hardening must not walk the whole shpc base, which grows with every module."""
    hardened: list[Path] = []
    monkeypatch.setattr(exposer_mod, "harden_tree", hardened.append)
    build(make(), UP, sif)
    assert set(hardened) == {
        gl.shpc_module_base() / URI,
        gl.shpc_wrapper_base() / URI,
        gl.shpc_container_base() / URI,
        gl.local_registry() / URI,
    }
    assert gl.shpc_base() not in hardened
    assert gl.shpc_module_base() not in hardened


def test_build_makes_the_module_usable_by_everyone(sif):
    link = build(make(shpc=StrictUmaskShpc()), UP, sif)
    module = gl.shpc_module_base() / URI / UP.raw / "module.lua"
    wrapper = gl.shpc_wrapper_base() / URI / UP.raw / "bin" / "samtools"
    assert mode(module) == 0o644
    assert mode(module.parent) == 0o755
    assert mode(wrapper) == 0o755, "wrappers must stay executable"
    assert mode(link.parent) == 0o755, "the Lmod modulefile directory too"


def test_build_makes_the_lmod_default_version_file_readable(sif):
    """shpc's ``.version`` sits beside the versions; unreadable, it breaks ``module load``."""
    build(make(shpc=StrictUmaskShpc()), UP, sif)
    assert mode(gl.shpc_module_base() / URI / ".version") == 0o644


def test_module_link_is_a_symlink_into_shpc(sif):
    """chmod follows symlinks, so the link itself is never a hardening target."""
    link = build(make(shpc=StrictUmaskShpc()), Tag(UP.raw), sif)
    assert link.is_symlink()
    assert link.resolve() == gl.shpc_module_base() / URI / UP.raw / "module.lua"
