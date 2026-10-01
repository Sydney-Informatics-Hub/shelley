#!/usr/bin/env python3
"""Coverage for the shared-permission helpers used by `shelley build`."""

import os
import stat
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shelley.utils import globals as gl
from shelley.utils.perms import (
    apply_build_umask,
    ensure_shared_dir,
    ensure_shared_layout,
    ensure_traversable,
    harden_tree,
    share_file,
)


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


@pytest.fixture
def restore_umask():
    previous = os.umask(0o022)
    yield
    os.umask(previous)


# ---------------------------------------------------------------------------
# apply_build_umask
# ---------------------------------------------------------------------------


def test_apply_build_umask_sets_022_and_returns_previous(restore_umask):
    os.umask(0o077)
    previous = apply_build_umask()

    assert previous == 0o077
    current = os.umask(0o022)  # read it back, then restore what we just set
    assert current == gl.SHARED_UMASK


# ---------------------------------------------------------------------------
# harden_tree
# ---------------------------------------------------------------------------


def _restrictive_tree(root: Path) -> dict[str, Path]:
    """Build a tree that mimics an shpc module dir created under `umask 077`."""
    module_dir = root / "quay.io" / "biocontainers" / "samtools" / "1.21"
    bin_dir = module_dir / "bin"
    bin_dir.mkdir(parents=True)

    lua = module_dir / "module.lua"
    lua.write_text("-- module\n")
    wrapper = bin_dir / "samtools"
    wrapper.write_text("#!/bin/bash\n")

    for d in (
        root,
        root / "quay.io",
        root / "quay.io" / "biocontainers",
        module_dir.parent,
        module_dir,
        bin_dir,
    ):
        os.chmod(d, 0o700)
    os.chmod(lua, 0o600)
    os.chmod(wrapper, 0o700)  # shpc marks wrapper scripts owner-executable

    return {
        "module_dir": module_dir,
        "bin_dir": bin_dir,
        "lua": lua,
        "wrapper": wrapper,
    }


def test_harden_tree_opens_dirs_and_files(tmp_path):
    root = tmp_path / "modules"
    root.mkdir()
    t = _restrictive_tree(root)

    harden_tree(root)

    assert mode_of(root) == 0o755
    assert mode_of(t["module_dir"]) == 0o755
    assert mode_of(t["bin_dir"]) == 0o755
    assert mode_of(t["lua"]) == 0o644


def test_harden_tree_propagates_owner_exec_to_group_and_other(tmp_path):
    """The X in `a+rX`: an owner-executable file becomes 0755, a plain file 0644."""
    root = tmp_path / "wrappers"
    root.mkdir()
    t = _restrictive_tree(root)

    harden_tree(root)

    assert mode_of(t["wrapper"]) == 0o755, (
        "wrapper scripts must stay executable, for everyone"
    )
    assert mode_of(t["lua"]) == 0o644, "a non-executable file must not gain +x"


def test_harden_tree_skips_symlinked_files(tmp_path):
    """os.chmod follows symlinks; hardening must never modify a link's target.

    Regression guard: module trees contain links out to read-only CVMFS SIFs.
    """
    root = tmp_path / "modules"
    root.mkdir()
    outside = tmp_path / "outside.sif"
    outside.write_text("container")
    os.chmod(outside, 0o600)

    (root / "container.sif").symlink_to(outside)

    harden_tree(root)

    assert mode_of(outside) == 0o600, "chmod leaked through the symlink to its target"


def test_harden_tree_skips_symlinked_dirs(tmp_path):
    root = tmp_path / "modules"
    root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    inner = outside_dir / "secret.txt"
    inner.write_text("x")
    os.chmod(inner, 0o600)
    os.chmod(outside_dir, 0o700)

    (root / "linked").symlink_to(outside_dir, target_is_directory=True)

    harden_tree(root)

    assert mode_of(outside_dir) == 0o700
    assert mode_of(inner) == 0o600


def test_harden_tree_missing_root_is_noop(tmp_path):
    harden_tree(tmp_path / "never-created")  # must not raise


def test_harden_tree_on_symlink_root_is_noop(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    os.chmod(target, 0o700)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    harden_tree(link)

    assert mode_of(target) == 0o700


# ---------------------------------------------------------------------------
# ensure_shared_dir / ensure_traversable
# ---------------------------------------------------------------------------


def test_ensure_shared_dir_is_0755_under_restrictive_umask(
    tmp_path, monkeypatch, restore_umask
):
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    os.umask(0o077)

    created = ensure_shared_dir(gl.shpc_module_base())

    assert created.is_dir()
    assert mode_of(created) == 0o755
    assert mode_of(gl.shpc_base()) == 0o755, "the parent must be traversable too"


def test_ensure_traversable_opens_intermediate_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    leaf = gl.shpc_module_base() / "quay.io" / "biocontainers" / "samtools" / "1.21"
    leaf.mkdir(parents=True)
    for d in (gl.shpc_base(), gl.shpc_module_base(), *leaf.parents):
        if gl.shpc_base() == d or gl.shpc_base() in d.parents:
            os.chmod(d, 0o700)
    os.chmod(leaf, 0o700)

    ensure_traversable(leaf)

    current = leaf
    while True:
        assert mode_of(current) & 0o055 == 0o055, (
            f"{current} is not group/other traversable"
        )
        if current == gl.shpc_base():
            break
        current = current.parent


def test_ensure_traversable_stops_at_the_build_root(tmp_path, monkeypatch):
    """Nothing above a build root may be touched — never /, /apps, or a home dir."""
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    os.chmod(tmp_path, 0o700)
    leaf = ensure_shared_dir(gl.shpc_module_base())

    ensure_traversable(leaf)

    assert mode_of(tmp_path) == 0o700, "chmod escaped above the build root"


def test_ensure_traversable_outside_build_roots_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()
    os.chmod(unrelated, 0o700)

    ensure_traversable(unrelated)

    assert mode_of(unrelated) == 0o700


def test_share_file_sets_0644_and_ignores_symlinks(tmp_path):
    target = tmp_path / "container.yaml"
    target.write_text("docker: quay.io/biocontainers/samtools\n")
    os.chmod(target, 0o600)

    share_file(target)
    assert mode_of(target) == 0o644

    outside = tmp_path / "outside.yaml"
    outside.write_text("x")
    os.chmod(outside, 0o600)
    link = tmp_path / "link.yaml"
    link.symlink_to(outside)

    share_file(link)
    assert mode_of(outside) == 0o600


# ---------------------------------------------------------------------------
# ensure_shared_layout
# ---------------------------------------------------------------------------


def test_ensure_shared_layout_creates_every_shared_dir(
    tmp_path, monkeypatch, restore_umask
):
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    monkeypatch.setenv("SHELLEY_LOCAL_REGISTRY", str(tmp_path / "local"))
    monkeypatch.setenv("SHELLEY_LMOD_MODULES_PATH", str(tmp_path / "modulefiles"))
    os.umask(0o077)

    ensure_shared_layout()

    expected = gl.shared_dirs()
    assert len(expected) == 7
    for path in expected:
        assert path.is_dir(), f"{path} was not created"
        assert mode_of(path) == 0o755, f"{path} is {oct(mode_of(path))}, not 0755"


def test_ensure_shared_layout_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    monkeypatch.setenv("SHELLEY_LOCAL_REGISTRY", str(tmp_path / "local"))
    monkeypatch.setenv("SHELLEY_LMOD_MODULES_PATH", str(tmp_path / "modulefiles"))

    ensure_shared_layout()
    ensure_shared_layout()  # must not raise

    for path in gl.shared_dirs():
        assert path.is_dir()
