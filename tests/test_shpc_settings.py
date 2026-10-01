#!/usr/bin/env python3
"""Coverage for the shelley-managed shpc settings file."""

import stat
import sys
from pathlib import Path

import pytest
import yaml

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shelley.builder.shpc_settings import (
    desired_registry,
    desired_settings,
    ensure_shared_shpc_settings,
)
from shelley.utils import globals as gl
from shelley.utils.perms import ensure_shared_layout

OVERRIDE_KEYS = {
    "module_base",
    "container_base",
    "wrapper_base",
    "views_base",
    "registry",
}


@pytest.fixture
def shared_base(tmp_path, monkeypatch):
    """Redirect the build roots into tmp_path and create the layout."""
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    monkeypatch.setenv("SHELLEY_LOCAL_REGISTRY", str(tmp_path / "local"))
    monkeypatch.setenv("SHELLEY_LMOD_MODULES_PATH", str(tmp_path / "modulefiles"))
    ensure_shared_layout()
    return tmp_path


# ---------------------------------------------------------------------------
# desired_settings
# ---------------------------------------------------------------------------


def test_only_the_override_keys_are_written(shared_base):
    assert set(desired_settings()) == OVERRIDE_KEYS


def test_all_paths_are_absolute_and_never_reference_home(shared_base):
    settings = desired_settings()

    for key in ("module_base", "container_base", "wrapper_base", "views_base"):
        assert Path(settings[key]).is_absolute(), f"{key} must be absolute"

    # The whole point of this file: shpc's own defaults are $HOME/shpc/*, which under
    # `sudo -E` land in the invoking user's unreadable home directory.
    assert "$HOME" not in yaml.dump(settings)
    assert "~" not in yaml.dump(settings)


def test_bases_live_under_the_shared_root(shared_base):
    settings = desired_settings()
    base = gl.shpc_base()

    assert settings["module_base"] == str(base / "modules")
    assert settings["container_base"] == str(base / "containers")
    assert settings["wrapper_base"] == str(base / "wrappers")
    assert settings["views_base"] == str(base / "views")


def test_registry_lists_local_before_upstream(shared_base):
    registry = desired_registry()

    assert registry == [str(gl.local_registry()), gl.UPSTREAM_SHPC_REGISTRY]


def test_registry_omits_a_missing_local_registry(tmp_path, monkeypatch):
    """A non-existent filesystem registry makes shpc raise on every command."""
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "shpc"))
    monkeypatch.setenv("SHELLEY_LOCAL_REGISTRY", str(tmp_path / "never-created"))

    assert desired_registry() == [gl.UPSTREAM_SHPC_REGISTRY]


# ---------------------------------------------------------------------------
# ensure_shared_shpc_settings
# ---------------------------------------------------------------------------


def test_writes_the_settings_file(shared_base):
    path = ensure_shared_shpc_settings()

    assert path == gl.shpc_settings_file()
    assert yaml.safe_load(path.read_text()) == desired_settings()
    assert path.read_text().startswith("# Managed by shelley")


def test_settings_file_is_world_readable(shared_base):
    path = ensure_shared_shpc_settings()

    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_is_idempotent_and_does_not_rewrite(shared_base):
    path = ensure_shared_shpc_settings()
    before = (path.read_bytes(), path.stat().st_mtime_ns)

    ensure_shared_shpc_settings()

    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_rewrites_a_stale_file(shared_base):
    path = ensure_shared_shpc_settings()
    path.write_text(yaml.dump({"module_base": "/somewhere/else"}))

    ensure_shared_shpc_settings()

    assert yaml.safe_load(path.read_text()) == desired_settings()


def test_rewrites_an_unparseable_file(shared_base):
    path = gl.shpc_settings_file()
    path.write_text("{ this is: not: valid yaml")

    ensure_shared_shpc_settings()

    assert yaml.safe_load(path.read_text()) == desired_settings()


def test_raises_when_the_base_is_not_writable(tmp_path, monkeypatch):
    """A bootstrap failure must be loud, never a silent fall back to $HOME."""
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    (readonly / "shpc").mkdir()
    readonly.chmod(0o500)
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(readonly / "shpc"))
    (readonly / "shpc").chmod(0o500)

    try:
        with pytest.raises(RuntimeError, match="shpc settings file"):
            ensure_shared_shpc_settings()
    finally:
        (readonly / "shpc").chmod(0o700)
        readonly.chmod(0o700)


# ---------------------------------------------------------------------------
# The partial file must actually be valid to the installed shpc
# ---------------------------------------------------------------------------


@pytest.mark.shpc
def test_shpc_accepts_the_partial_file_and_honours_the_override(shared_base):
    """The one test that catches an upstream shpc schema or precedence change."""
    pytest.importorskip("shpc.main.settings")
    from shpc.main.settings import Settings

    path = ensure_shared_shpc_settings()
    settings = Settings(str(path))

    assert settings.get("module_base") == str(gl.shpc_module_base())
    assert settings.get("wrapper_base") == str(gl.shpc_wrapper_base())
    assert str(gl.local_registry()) in settings.get("registry")
    # A key shelley does not override must still come from shpc's defaults.
    assert settings.get("module_sys") is not None
