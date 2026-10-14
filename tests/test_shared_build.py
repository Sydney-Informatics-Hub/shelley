"""The sudo probe: a build or clean elevates unless it can write every shared root.

The build core's shared-VM behaviour is covered in
``tests/build_core/test_exposer_sharing.py``.
"""

from unittest.mock import patch

from shelley.privilege import needs_root, sudo_env_args

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
