#!/usr/bin/env python3
"""Coverage for the shared, multi-user build behaviour of `shelley build`.

These lock in the properties that make a built module usable by every user on the
machine: shpc is pinned to the shared settings file, artifacts are hardened rather than
chowned to the builder, and the sudo probe covers every root a build must write to.
"""

import os
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shelley.builder.cvmfs_builder import CVMFSModuleBuilder, _shpc_cmd
from shelley.commands.build import needs_sudo, sudo_env_args
from shelley.utils import globals as gl

TOOL, VERSION = "samtools", "1.21--h96c455f_1"
URI = f"quay.io/biocontainers/{TOOL}"


@pytest.fixture
def builder(tmp_path) -> CVMFSModuleBuilder:
    return CVMFSModuleBuilder(lmod_modules=str(tmp_path / "modulefiles"))


def _install_tree(module_base: Path) -> Path:
    """Create the module.lua an `shpc install` would have produced."""
    src = module_base / "quay.io" / "biocontainers" / TOOL / VERSION / "module.lua"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("-- module\n")
    return src


def _fake_run(module_base: Path, calls: list | None = None):
    """subprocess.run side effect covering shpc install / uninstall / config."""

    def run(cmd, **_):
        if calls is not None:
            calls.append(list(cmd))
        m = MagicMock()
        m.stderr = ""
        m.returncode = 0
        m.stdout = str(module_base) if "module_base" in cmd else "Module was created.\n"
        return m

    return run


def _upstream_config():
    return {"tags": {VERSION: "sha256:x"}, "aliases": {TOOL: f"/usr/local/bin/{TOOL}"}}


# ---------------------------------------------------------------------------
# shpc is always pinned to the shared settings file
# ---------------------------------------------------------------------------


def test_shpc_cmd_pins_the_shared_settings_file():
    cmd = _shpc_cmd("install", "quay.io/biocontainers/samtools:1.21")

    assert cmd[1:3] == ["--settings-file", str(gl.shpc_settings_file())]
    assert cmd[3:] == ["install", "quay.io/biocontainers/samtools:1.21"]


def test_shpc_cmd_omits_the_flag_when_the_file_is_absent(tmp_path, monkeypatch):
    """shpc hard-exits on a missing --settings-file, so read-only callers degrade."""
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "never-created"))

    cmd = _shpc_cmd("config", "get", "module_base")

    assert "--settings-file" not in cmd
    assert cmd[1:] == ["config", "get", "module_base"]


def test_every_shpc_call_in_an_install_carries_the_settings_file(builder, tmp_path):
    module_base = tmp_path / "shpc_modules"
    _install_tree(module_base)
    calls: list[list[str]] = []

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_fake_run(module_base, calls),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value=_upstream_config(),
        ),
    ):
        builder.shpc_install(TOOL, VERSION)

    shpc_calls = [c for c in calls if "shpc" in c[0]]
    assert shpc_calls, "expected at least one shpc invocation"
    for call in shpc_calls:
        assert "--settings-file" in call, f"unpinned shpc call: {call}"


# ---------------------------------------------------------------------------
# No chown: artifacts stay root-owned and are hardened instead
# ---------------------------------------------------------------------------


def test_install_never_chowns_the_tree(builder, tmp_path, monkeypatch):
    """Handing the tree to $SUDO_USER is what made builds single-user."""
    module_base = tmp_path / "shpc_modules"
    _install_tree(module_base)
    calls: list[list[str]] = []
    monkeypatch.setenv("SUDO_USER", "ubuntu")

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_fake_run(module_base, calls),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value=_upstream_config(),
        ),
        patch("os.getuid", return_value=0),
    ):
        builder.shpc_install(TOOL, VERSION)

    assert not any("chown" in os.path.basename(c[0]) for c in calls), (
        f"a chown was still spawned: {calls}"
    )


def test_install_hardens_this_tools_subtrees_only(builder, tmp_path):
    """Hardening must not walk the whole shpc base — that grows with every module."""
    module_base = tmp_path / "shpc_modules"
    _install_tree(module_base)

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_fake_run(module_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value=_upstream_config(),
        ),
        patch("shelley.builder.cvmfs_builder.harden_tree") as mock_harden,
    ):
        builder.shpc_install(TOOL, VERSION)

    hardened = {Path(c.args[0]) for c in mock_harden.call_args_list}
    assert hardened == {
        module_base / "quay.io" / "biocontainers" / TOOL,
        gl.shpc_wrapper_base() / "quay.io" / "biocontainers" / TOOL,
        gl.shpc_container_base() / "quay.io" / "biocontainers" / TOOL,
        gl.local_registry() / URI,
    }
    assert gl.shpc_base() not in hardened
    assert module_base not in hardened, "must not walk every installed module"


def test_install_hardens_the_lmod_default_version_file(builder, tmp_path):
    """shpc's `.version` sits beside the versions; unreadable, it breaks `module load`."""
    module_base = tmp_path / "shpc_modules"
    src = _install_tree(module_base)
    dotversion = src.parent.parent / ".version"
    dotversion.write_text('set ModulesVersion "x"\n')
    os.chmod(dotversion, 0o600)

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_fake_run(module_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value=_upstream_config(),
        ),
    ):
        builder.shpc_install(TOOL, VERSION)

    assert stat.S_IMODE(dotversion.stat().st_mode) == 0o644


def test_install_makes_the_module_world_readable(builder, tmp_path):
    """End to end on the permission bits: a 0600 module.lua becomes 0644."""
    module_base = tmp_path / "shpc_modules"
    src = _install_tree(module_base)
    wrapper = src.parent / "bin" / TOOL
    wrapper.parent.mkdir()
    wrapper.write_text("#!/bin/bash\n")
    os.chmod(src, 0o600)
    os.chmod(wrapper, 0o700)
    os.chmod(src.parent, 0o700)

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_fake_run(module_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value=_upstream_config(),
        ),
    ):
        dest = builder.shpc_install(TOOL, VERSION)

    assert stat.S_IMODE(src.stat().st_mode) == 0o644
    assert stat.S_IMODE(wrapper.stat().st_mode) == 0o755, (
        "wrappers must stay executable"
    )
    assert stat.S_IMODE(src.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o755, "the modulefiles dir too"


def test_module_symlink_is_created_and_not_chmodded_through(builder, tmp_path):
    """chmod follows symlinks; the .lua link must never be a chmod target."""
    module_base = tmp_path / "shpc_modules"
    src = _install_tree(module_base)
    os.chmod(src, 0o644)

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_fake_run(module_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value=_upstream_config(),
        ),
        patch("shelley.builder.cvmfs_builder.share_file") as mock_share_file,
    ):
        dest = builder.shpc_install(TOOL, VERSION)

    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    assert dest not in [Path(c.args[0]) for c in mock_share_file.call_args_list]


# ---------------------------------------------------------------------------
# module_base resolution
# ---------------------------------------------------------------------------


def test_module_base_falls_back_when_shpc_cannot_report_it(builder, tmp_path):
    """A failed `config get` must not raise after a successful install."""
    _install_tree(gl.shpc_module_base())

    def run(cmd, **_):
        m = MagicMock()
        m.stderr = ""
        if "module_base" in cmd:
            m.returncode = 1
            m.stdout = ""
        else:
            m.returncode = 0
            m.stdout = "Module was created.\n"
        return m

    with (
        patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=run),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value=_upstream_config(),
        ),
    ):
        dest = builder.shpc_install(TOOL, VERSION)

    assert (
        dest.resolve()
        == (
            gl.shpc_module_base()
            / "quay.io"
            / "biocontainers"
            / TOOL
            / VERSION
            / "module.lua"
        ).resolve()
    )


# ---------------------------------------------------------------------------
# The local registry entry
# ---------------------------------------------------------------------------


def test_local_container_yaml_is_world_readable(builder, tmp_path):
    module_base = tmp_path / "shpc_modules"
    _install_tree(module_base)

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_fake_run(module_base),
        ),
        patch("shelley.builder.cvmfs_builder._load_registry_config", return_value={}),
        patch(
            "shelley.builder.cvmfs_builder.extract_aliases",
            return_value=[{"name": TOOL, "command": f"/usr/local/bin/{TOOL}"}],
        ),
        patch.object(builder, "_compute_sha256", return_value="deadbeef"),
        patch("shelley.builder.cvmfs_builder.console"),
    ):
        builder.shpc_install(TOOL, VERSION)

    written = gl.local_registry() / URI / "container.yaml"
    assert written.is_file()
    assert stat.S_IMODE(written.stat().st_mode) == 0o644


def test_registering_the_local_registry_does_not_shell_out(builder):
    """`shpc config add registry` would expand our override file into a full snapshot."""
    with patch("shelley.builder.cvmfs_builder.subprocess.run") as mock_run:
        builder._register_local_registry(str(gl.local_registry()))

    mock_run.assert_not_called()
    assert gl.local_registry().is_dir()
    assert str(gl.local_registry()) in gl.shpc_settings_file().read_text()


# ---------------------------------------------------------------------------
# The sudo probe
# ---------------------------------------------------------------------------


def test_needs_sudo_when_a_build_root_is_missing(tmp_path, monkeypatch):
    """First run on a fresh machine: /apps/shpc does not exist yet."""
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "never-created"))

    assert needs_sudo() is True


def test_needs_sudo_when_a_build_root_is_not_writable(tmp_path, monkeypatch):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    monkeypatch.setenv("SHELLEY_LOCAL_REGISTRY", str(readonly))
    readonly.chmod(0o500)

    try:
        with patch("os.geteuid", return_value=1000):
            assert needs_sudo() is True
    finally:
        readonly.chmod(0o700)


def test_no_sudo_when_every_root_is_writable(tmp_path, monkeypatch):
    with patch("os.geteuid", return_value=1000):
        assert needs_sudo() is False, "the conftest redirect makes all roots writable"


def test_no_sudo_when_already_root():
    with patch("os.geteuid", return_value=0):
        assert needs_sudo() is False


def test_sudo_reexec_forwards_the_shelley_overrides(monkeypatch):
    """`sudo -E` needs SETENV privilege, so pass the overrides explicitly too."""
    monkeypatch.setenv("SHELLEY_SHPC_BASE", "/scratch/shpc")

    args = sudo_env_args()

    assert args[0].startswith("PATH=")
    assert "SHELLEY_SHPC_BASE=/scratch/shpc" in args


# ---------------------------------------------------------------------------
# find: a module symlinked into an unreadable tree is not "installed"
# ---------------------------------------------------------------------------


def test_find_reports_a_resolvable_modulefile_as_installed():
    from shelley.commands.find import module_is_installed

    target = (
        gl.shpc_module_base()
        / "quay.io"
        / "biocontainers"
        / TOOL
        / VERSION
        / "module.lua"
    )
    target.parent.mkdir(parents=True)
    target.write_text("-- module\n")
    link_dir = gl.lmod_modules() / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(target)

    assert module_is_installed(TOOL, "1.21") is True


def test_find_does_not_report_a_dangling_modulefile_as_installed():
    """Modules built before the shared layout point into the builder's home.

    Those symlinks still exist, so a name-only check reports them as installed even
    though `module load` fails for everyone but the original builder.
    """
    from shelley.commands.find import module_is_installed

    link_dir = gl.lmod_modules() / TOOL
    link_dir.mkdir(parents=True)
    (link_dir / f"{VERSION}.lua").symlink_to(
        "/home/someone-else/shpc/modules/module.lua"
    )

    assert module_is_installed(TOOL, "1.21") is False


def test_find_reports_nothing_when_the_tool_was_never_built():
    from shelley.commands.find import module_is_installed

    assert module_is_installed("never-built", "1.0") is False
