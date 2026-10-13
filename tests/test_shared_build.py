"""Shared, multi-user behaviour outside the build core.

shpc calls made by the old ``clean`` path are pinned to the shared settings file; the
sudo probe covers every root a build must write to; ``find`` only counts modules every
user can load. The build itself is covered in ``tests/build_core/test_exposer_sharing.py``.
"""

from unittest.mock import patch

from shelley.builder.cvmfs_builder import _shpc_cmd
from shelley.privilege import needs_root, sudo_env_args
from shelley.utils import globals as gl

TOOL, VERSION = "samtools", "1.21--h96c455f_1"


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


# ---------------------------------------------------------------------------
# The sudo probe
# ---------------------------------------------------------------------------


def test_needs_root_when_a_build_root_is_missing(tmp_path, monkeypatch):
    """First run on a fresh machine: /apps/shpc does not exist yet."""
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(tmp_path / "never-created"))

    assert needs_root() is True


def test_needs_root_when_a_build_root_is_not_writable(tmp_path, monkeypatch):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    monkeypatch.setenv("SHELLEY_LOCAL_REGISTRY", str(readonly))
    readonly.chmod(0o500)

    try:
        with patch("os.geteuid", return_value=1000):
            assert needs_root() is True
    finally:
        readonly.chmod(0o700)


def test_no_root_needed_when_every_root_is_writable(tmp_path, monkeypatch):
    with patch("os.geteuid", return_value=1000):
        assert needs_root() is False, "the conftest redirect makes all roots writable"


def test_no_root_needed_when_already_root():
    with patch("os.geteuid", return_value=0):
        assert needs_root() is False


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
