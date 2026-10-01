"""Tests for `shelley update` (self-upgrade command).

No real subprocess or network: subprocess.run and install-mode detection are
monkeypatched so command construction and exit-code handling are tested in
isolation.
"""

from unittest.mock import MagicMock, patch

from shelley.commands import update

# ---------------------------------------------------------------------------
# _find_uv — PATH first, BioShell fallback, else None
# ---------------------------------------------------------------------------


def test_find_uv_prefers_path(monkeypatch):
    monkeypatch.setattr(update.shutil, "which", lambda _: "/home/u/.local/bin/uv")
    assert update._find_uv() == "/home/u/.local/bin/uv"


def test_find_uv_falls_back_to_system(monkeypatch):
    monkeypatch.setattr(update.shutil, "which", lambda _: None)
    monkeypatch.setattr(update.Path, "exists", lambda self: True)
    assert update._find_uv() == update.SYSTEM_UV


def test_find_uv_none_when_missing(monkeypatch):
    monkeypatch.setattr(update.shutil, "which", lambda _: None)
    monkeypatch.setattr(update.Path, "exists", lambda self: False)
    assert update._find_uv() is None


# ---------------------------------------------------------------------------
# _build_upgrade_cmd — correct argv per install mode (uv path passed in)
# ---------------------------------------------------------------------------


def test_build_cmd_per_user(monkeypatch):
    monkeypatch.setattr(update, "_is_system_install", lambda: False)
    cmd = update._build_upgrade_cmd("/home/u/.local/bin/uv")
    assert cmd == ["/home/u/.local/bin/uv", "tool", "upgrade", "shelley"]
    assert "sudo" not in cmd


def test_build_cmd_system(monkeypatch):
    monkeypatch.setattr(update, "_is_system_install", lambda: True)
    cmd = update._build_upgrade_cmd(update.SYSTEM_UV)
    assert cmd[0] == "sudo"
    assert update.SYSTEM_UV in cmd
    assert f"UV_TOOL_DIR={update.SYSTEM_TOOL_DIR}" in cmd
    assert f"UV_TOOL_BIN_DIR={update.SYSTEM_BIN_DIR}" in cmd
    assert cmd[-3:] == ["tool", "upgrade", "shelley"]


# ---------------------------------------------------------------------------
# _is_system_install — detection from package location
# ---------------------------------------------------------------------------


def test_is_system_install_true(monkeypatch):
    monkeypatch.setattr(
        update, "__file__", f"{update.SYSTEM_TOOL_DIR}/shelley/commands/update.py"
    )
    assert update._is_system_install() is True


def test_is_system_install_false(monkeypatch):
    monkeypatch.setattr(
        update, "__file__", "/home/u/.local/share/uv/tools/shelley/commands/update.py"
    )
    assert update._is_system_install() is False


# ---------------------------------------------------------------------------
# update_shelley — returns the subprocess exit code, handles missing binaries
# ---------------------------------------------------------------------------


def _stub_resolution(monkeypatch):
    """Make update_shelley reach subprocess: uv found, per-user, fixed cmd."""
    monkeypatch.setattr(update, "_find_uv", lambda: "uv")
    monkeypatch.setattr(update, "_is_system_install", lambda: False)
    monkeypatch.setattr(
        update, "_build_upgrade_cmd", lambda uv: [uv, "tool", "upgrade", "shelley"]
    )


def test_update_returns_subprocess_returncode(monkeypatch):
    _stub_resolution(monkeypatch)
    with patch.object(
        update.subprocess, "run", return_value=MagicMock(returncode=0)
    ) as run:
        assert update.update_shelley() == 0
        run.assert_called_once()


def test_update_propagates_failure_code(monkeypatch):
    _stub_resolution(monkeypatch)
    with patch.object(update.subprocess, "run", return_value=MagicMock(returncode=2)):
        assert update.update_shelley() == 2


def test_update_errors_when_uv_not_found(monkeypatch):
    monkeypatch.setattr(update, "_find_uv", lambda: None)
    with patch.object(update.subprocess, "run") as run:
        assert update.update_shelley() == 1
        run.assert_not_called()  # bail out before trying to run anything


def test_update_handles_missing_sudo(monkeypatch):
    _stub_resolution(monkeypatch)
    with patch.object(update.subprocess, "run", side_effect=FileNotFoundError("sudo")):
        assert update.update_shelley() == 1
