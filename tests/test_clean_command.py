#!/usr/bin/env python3
"""Tests for `shelley clean` — the inverse of `shelley build`."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shelley.builder.cvmfs_builder import CVMFSModuleBuilder
from shelley.commands.clean import (
    _not_installed_panel, _resolve_installed_version, clean_module,
)
from shelley.commands.find import list_installed_versions
from shelley.utils import globals as gl
from shelley.utils.style import console, ShelleyStyle

TOOL, VERSION = "samtools", "1.21--h96c455f_1"
URI = f"quay.io/biocontainers/{TOOL}"
URI_TAG = f"{URI}:{VERSION}"


def _fake_run(returncode: int = 0, output: str = "", calls: list | None = None):
    """subprocess.run side effect covering `shpc uninstall`."""
    def run(cmd, **_):
        if calls is not None:
            calls.append(list(cmd))
        m = MagicMock()
        m.returncode = returncode
        m.stdout = output
        m.stderr = ""
        return m
    return run


def _registry_yaml(tags: dict, aliases=None) -> Path:
    registry_dir = gl.local_registry() / URI
    registry_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = registry_dir / "container.yaml"
    config = {
        "docker": URI,
        "tags": tags,
        "aliases": aliases or [{"name": TOOL, "command": f"/usr/local/bin/{TOOL}"}],
    }
    with open(yaml_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return yaml_path


def _touch_modulefile(tool: str, version: str) -> Path:
    """Create an installed modulefile marker under the (conftest-redirected) shared root."""
    d = gl.lmod_modules() / tool
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{version}.lua"
    path.write_text("-- module\n")
    return path


# ---------------------------------------------------------------------------
# CVMFSModuleBuilder.uninstall_module
# ---------------------------------------------------------------------------

@pytest.fixture
def builder(tmp_path) -> CVMFSModuleBuilder:
    return CVMFSModuleBuilder(lmod_modules=str(tmp_path / "modulefiles"))


def test_uninstall_removes_modulefile_symlink_and_calls_shpc_uninstall(builder, tmp_path):
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    target = tmp_path / "module.lua"
    target.write_text("-- module\n")
    link = link_dir / f"{VERSION}.lua"
    link.symlink_to(target)

    calls: list[list[str]] = []
    with patch("shelley.builder.cvmfs_builder.subprocess.run",
               side_effect=_fake_run(0, "Module was uninstalled.\n", calls)):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["shpc_removed"] is True
    assert report["modulefile_removed"] is True
    assert not link.exists() and not link.is_symlink()
    assert any("uninstall" in c and "--force" in c and URI_TAG in c for c in calls)


def test_uninstall_dangling_symlink_only(builder):
    """shpc has nothing to remove, but shelley's own symlink must still go."""
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    link = link_dir / f"{VERSION}.lua"
    link.symlink_to(link_dir / "does-not-exist.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run",
               side_effect=_fake_run(1, "not found in module_base\n")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["shpc_removed"] is False
    assert report["modulefile_removed"] is True
    assert not link.is_symlink()


def test_uninstall_prunes_the_now_empty_tool_directory(builder):
    """The parent tool dir under lmod_modules must not linger once its last version goes."""
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(link_dir / "does-not-exist.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        builder.uninstall_module(TOOL, VERSION)

    assert not link_dir.exists()


def test_uninstall_keeps_the_tool_directory_when_other_versions_remain(builder):
    other_version = "1.20--abc"
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(link_dir / "does-not-exist.lua")
    (link_dir / f"{other_version}.lua").symlink_to(link_dir / "also-missing.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        builder.uninstall_module(TOOL, VERSION)

    assert link_dir.is_dir()
    assert (link_dir / f"{other_version}.lua").is_symlink()


def test_uninstall_never_touches_the_local_registry_cache(builder):
    """Without a marker directory, container.yaml is a shared upstream cache/mirror,
    not per-version state — clean must leave it byte-for-byte alone, even when it
    happens to list this version."""
    registry_yaml = _registry_yaml({VERSION: "sha256:aaa", "1.20--abc": "sha256:bbb"})
    before = registry_yaml.read_text()

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        builder.uninstall_module(TOOL, VERSION)

    assert registry_yaml.read_text() == before


def test_uninstall_prunes_the_tag_when_a_marker_directory_proves_it_was_local(builder):
    """A registry_dir/<version>/ marker (left by _ensure_local_registry_entry when the
    tag was absent upstream) proves this one tag is safe to remove — everything else
    in container.yaml must be left alone, and the file itself is never deleted."""
    other_version = "1.20--abc"
    registry_yaml = _registry_yaml({VERSION: "sha256:aaa", other_version: "sha256:bbb"})
    marker_dir = gl.local_registry() / URI / VERSION
    marker_dir.mkdir(parents=True)

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["registry_tag_removed"] is True
    assert not marker_dir.exists()
    assert registry_yaml.is_file()
    config = yaml.safe_load(registry_yaml.read_text())
    assert config["tags"] == {other_version: "sha256:bbb"}
    assert config["aliases"]


def test_uninstall_removes_marker_but_keeps_upstream_tag(builder):
    """A marker created for an interactively-edited but genuinely-upstream version
    (in_upstream=True in its aliases.yaml snapshot) must be removed by clean, but
    the tag itself — real upstream data, not a local addition — must stay."""
    other_version = "1.20--abc"
    registry_yaml = _registry_yaml({VERSION: "sha256:aaa", other_version: "sha256:bbb"})
    marker_dir = gl.local_registry() / URI / VERSION
    marker_dir.mkdir(parents=True)
    (marker_dir / "aliases.yaml").write_text(
        yaml.dump({"version": VERSION, "aliases": [], "in_upstream": True})
    )

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert not marker_dir.exists()
    assert report["registry_tag_removed"] is False
    config = yaml.safe_load(registry_yaml.read_text())
    assert config["tags"] == {VERSION: "sha256:aaa", other_version: "sha256:bbb"}


def test_uninstall_marker_present_but_no_container_yaml_is_a_noop(builder):
    """A leftover marker with no container.yaml (already removed by hand, say) must
    not raise."""
    marker_dir = gl.local_registry() / URI / VERSION
    marker_dir.mkdir(parents=True)

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["registry_tag_removed"] is False
    assert not marker_dir.exists()


def test_uninstall_deletes_whole_registry_entry_when_last_version_cleaned(builder):
    """Regression for the real star-fusion case: container.yaml still had genuine
    upstream-cached tags for other versions, and no marker directory at all, yet
    once the tool has zero installed versions left the whole entry must go."""
    registry_yaml = _registry_yaml({
        VERSION: "sha256:aaa",
        "1.20--abc": "sha256:bbb",
        "1.19--def": "sha256:ccc",
    })
    registry_dir = registry_yaml.parent
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(link_dir / "does-not-exist.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["registry_entry_deleted"] is True
    assert report["registry_tag_removed"] is False
    assert not registry_dir.exists()


def test_uninstall_deletes_whole_registry_entry_including_marker_dir(builder):
    """The whole-entry deletion must also sweep up a leftover marker directory,
    without running the per-tag marker logic first."""
    registry_yaml = _registry_yaml({VERSION: "sha256:aaa"})
    registry_dir = registry_yaml.parent
    marker_dir = registry_dir / VERSION
    marker_dir.mkdir(parents=True)
    (marker_dir / "aliases.yaml").write_text(
        yaml.dump({"version": VERSION, "aliases": [], "in_upstream": False})
    )
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(link_dir / "does-not-exist.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["registry_entry_deleted"] is True
    assert report["registry_tag_removed"] is False
    assert not registry_dir.exists()
    assert not marker_dir.exists()


def test_uninstall_keeps_registry_entry_when_sibling_versions_remain(builder):
    """Regression guard: with other installed versions of the tool, the whole-entry
    deletion must not fire and container.yaml must stay byte-for-byte untouched."""
    other_version = "1.20--abc"
    registry_yaml = _registry_yaml({VERSION: "sha256:aaa", other_version: "sha256:bbb"})
    before = registry_yaml.read_text()
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(link_dir / "does-not-exist.lua")
    (link_dir / f"{other_version}.lua").symlink_to(link_dir / "also-missing.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["registry_entry_deleted"] is False
    assert registry_yaml.read_text() == before


def test_uninstall_registry_entry_deletion_is_noop_when_directory_never_existed(builder):
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(link_dir / "does-not-exist.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["registry_entry_deleted"] is False


def test_uninstall_deletes_registry_entry_directory_with_no_container_yaml(builder):
    """A stray marker directory with no container.yaml still gets swept up once
    this was the last installed version."""
    registry_dir = gl.local_registry() / URI
    marker_dir = registry_dir / VERSION
    marker_dir.mkdir(parents=True)
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(link_dir / "does-not-exist.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["registry_entry_deleted"] is True
    assert not registry_dir.exists()


def test_uninstall_detects_last_version_even_when_this_calls_own_modulefile_already_missing(builder):
    """tool_dir is otherwise empty but this version's own .lua was never there
    (e.g. a previous partial clean) — must still be detected as the last version."""
    registry_yaml = _registry_yaml({VERSION: "sha256:aaa"})
    registry_dir = registry_yaml.parent
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(0, "")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["modulefile_removed"] is False
    assert not link_dir.exists()
    assert report["registry_entry_deleted"] is True
    assert not registry_dir.exists()


def test_uninstall_removes_shelley_state_even_when_shpc_uninstall_fails(builder):
    """shpc failing to find its own entry must not block the rest of the cleanup."""
    link_dir = builder.lmod_modules_path / TOOL
    link_dir.mkdir(parents=True)
    link = link_dir / f"{VERSION}.lua"
    link.symlink_to(link_dir / "does-not-exist.lua")

    with patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=_fake_run(1, "boom")):
        report = builder.uninstall_module(TOOL, VERSION)

    assert report["shpc_removed"] is False
    assert report["modulefile_removed"] is True
    assert not link_dir.exists()


# ---------------------------------------------------------------------------
# Version resolution against what's actually installed
# ---------------------------------------------------------------------------

def test_resolve_installed_version_matches_short_and_full():
    _touch_modulefile(TOOL, "1.22--hdfd78af_0")

    assert _resolve_installed_version(TOOL, "1.22") == "1.22--hdfd78af_0"
    assert _resolve_installed_version(TOOL, "1.22--hdfd78af_0") == "1.22--hdfd78af_0"


def test_resolve_installed_version_raises_when_not_installed():
    with pytest.raises(ValueError):
        _resolve_installed_version(TOOL, "9.9")


def test_resolve_installed_version_raises_when_ambiguous():
    _touch_modulefile(TOOL, "1.21--aaa")
    _touch_modulefile(TOOL, "1.21--bbb")

    with pytest.raises(ValueError) as exc:
        _resolve_installed_version(TOOL, "1.21")
    assert "1.21--aaa" in str(exc.value)
    assert "1.21--bbb" in str(exc.value)


def test_list_installed_versions_includes_dangling_symlinks():
    d = gl.lmod_modules() / TOOL
    d.mkdir(parents=True)
    (d / f"{VERSION}.lua").symlink_to(d / "nowhere.lua")

    assert list_installed_versions(TOOL) == [VERSION]


def test_not_installed_panel_lists_installed_versions():
    _touch_modulefile(TOOL, VERSION)

    with console.capture() as cap:
        console.print(_not_installed_panel(TOOL, None))

    assert VERSION in cap.get()


# ---------------------------------------------------------------------------
# clean_module end to end
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_clean_builder():
    """Patch CVMFSModuleBuilder inside clean.py with a mock instance (no sudo needed)."""
    fake_builder = MagicMock(spec=CVMFSModuleBuilder)
    fake_builder.uninstall_module.return_value = {
        "uri_tag": URI_TAG, "shpc_removed": True, "shpc_output": "",
        "modulefile_removed": True, "registry_tag_removed": False,
        "registry_entry_deleted": False,
    }

    with patch("shelley.commands.clean.CVMFSModuleBuilder", return_value=fake_builder), \
         patch("shelley.commands.clean.ShelleyStyle.create_status") as mock_status, \
         patch("shelley.commands.clean.console"), \
         patch("shelley.commands.clean.load_build_modules"), \
         patch("shelley.commands.clean.apply_build_umask"), \
         patch("shelley.commands.clean.needs_sudo", return_value=False):
        mock_status.return_value.__enter__ = MagicMock(return_value=None)
        mock_status.return_value.__exit__ = MagicMock(return_value=False)
        yield fake_builder


def test_clean_module_happy_path_removes_everything(mock_clean_builder):
    _touch_modulefile(TOOL, VERSION)

    result = clean_module(f"{TOOL}:{VERSION}", force=True)

    assert result is True
    mock_clean_builder.uninstall_module.assert_called_once_with(TOOL, VERSION)


def test_clean_module_warns_when_shpc_uninstall_reports_failure(mock_clean_builder):
    _touch_modulefile(TOOL, VERSION)
    mock_clean_builder.uninstall_module.return_value = {
        "uri_tag": URI_TAG, "shpc_removed": False, "shpc_output": "boom",
        "modulefile_removed": True,
    }

    with patch("shelley.commands.clean.ShelleyStyle.create_warning_panel") as mock_warning:
        result = clean_module(f"{TOOL}:{VERSION}", force=True)

    assert result is True
    mock_warning.assert_called_once()


def test_clean_module_errors_with_no_version(mock_clean_builder):
    _touch_modulefile(TOOL, VERSION)

    result = clean_module(TOOL)

    assert result is False
    mock_clean_builder.uninstall_module.assert_not_called()


def test_clean_module_errors_when_version_not_installed(mock_clean_builder):
    _touch_modulefile(TOOL, "9.9--zzz")

    result = clean_module(f"{TOOL}:1.0")

    assert result is False
    mock_clean_builder.uninstall_module.assert_not_called()


def test_clean_module_force_skips_confirmation_prompt(mock_clean_builder):
    _touch_modulefile(TOOL, VERSION)

    with patch("shelley.commands.clean.questionary.confirm") as mock_confirm:
        result = clean_module(f"{TOOL}:{VERSION}", force=True)

    assert result is True
    mock_confirm.assert_not_called()


def test_clean_module_prompts_when_not_forced_and_user_declines(mock_clean_builder):
    _touch_modulefile(TOOL, VERSION)

    with patch("shelley.commands.clean.questionary.confirm") as mock_confirm:
        mock_confirm.return_value.ask.return_value = False
        result = clean_module(f"{TOOL}:{VERSION}")

    assert result is False
    mock_clean_builder.uninstall_module.assert_not_called()


def test_clean_module_prompts_when_not_forced_and_user_confirms(mock_clean_builder):
    _touch_modulefile(TOOL, VERSION)

    with patch("shelley.commands.clean.questionary.confirm") as mock_confirm:
        mock_confirm.return_value.ask.return_value = True
        result = clean_module(f"{TOOL}:{VERSION}")

    assert result is True
    mock_clean_builder.uninstall_module.assert_called_once_with(TOOL, VERSION)


def test_clean_module_reexecs_under_sudo_with_force_and_resolved_full_version():
    """The short version is resolved and confirmation happens before the re-exec;
    the elevated child is always invoked with -y."""
    _touch_modulefile(TOOL, VERSION)

    with patch("shelley.commands.clean.needs_sudo", return_value=True), \
         patch("shelley.commands.clean.reexec_command",
               return_value=[sys.executable, "-m", "shelley"]), \
         patch("shelley.commands.clean.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = clean_module(f"{TOOL}:1.21", force=True)

    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[-3:] == ["clean", f"{TOOL}:{VERSION}", "-y"]


# ---------------------------------------------------------------------------
# CLI dispatch: `shelley clean` with no args must not fall through to
# "Unknown Command" the way bare `shelley build` currently does.
# ---------------------------------------------------------------------------

def test_cli_clean_missing_args_exits_with_usage(monkeypatch):
    from shelley.client.cli import main

    monkeypatch.setattr(sys, "argv", ["shelley", "clean"])

    with patch("shelley.client.cli.clean_module") as mock_clean, \
         patch("shelley.client.cli.console"):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
    mock_clean.assert_not_called()


def test_cli_clean_dispatches_to_clean_module(monkeypatch):
    from shelley.client.cli import main

    monkeypatch.setattr(sys, "argv", ["shelley", "clean", f"{TOOL}:{VERSION}", "-y"])

    with patch("shelley.client.cli.clean_module", return_value=True) as mock_clean:
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 0
    mock_clean.assert_called_once_with(f"{TOOL}:{VERSION}", force=True)


# ---------------------------------------------------------------------------
# ShelleyStyle.create_clean_success rendering
# ---------------------------------------------------------------------------

def test_create_clean_success_mentions_registry_entry_deleted():
    report = {
        "shpc_removed": True, "modulefile_removed": True,
        "registry_tag_removed": False, "registry_entry_deleted": True,
    }

    with console.capture() as cap:
        console.print(ShelleyStyle.create_clean_success(TOOL, VERSION, report))

    assert "local registry entry" in cap.get()


def test_create_clean_success_still_mentions_registry_tag_removed():
    report = {
        "shpc_removed": True, "modulefile_removed": True,
        "registry_tag_removed": True, "registry_entry_deleted": False,
    }

    with console.capture() as cap:
        console.print(ShelleyStyle.create_clean_success(TOOL, VERSION, report))

    assert "local registry tag" in cap.get()
