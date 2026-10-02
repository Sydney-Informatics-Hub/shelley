"""Tests for the 'newer version available on main' update check.

All tests avoid real network by monkeypatching fetch_main_version, and isolate
the daily cache with a tmp XDG_CACHE_HOME so runs never touch the real cache.
"""

from unittest.mock import patch

import pytest

from shelley.utils import update_check


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Point the cache at a throwaway dir and clear the opt-out env."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv(update_check.OPT_OUT_ENV, raising=False)


# ---------------------------------------------------------------------------
# _is_newer — version comparison
# ---------------------------------------------------------------------------


def test_is_newer_true():
    assert update_check._is_newer("0.3.0", "0.2.0") is True


def test_is_newer_false_when_equal():
    assert update_check._is_newer("0.2.0", "0.2.0") is False


def test_is_newer_false_when_older():
    assert update_check._is_newer("0.1.0", "0.2.0") is False


def test_is_newer_dev_precedes_release():
    # PEP 440: 0.2.0.dev0 < 0.2.0, so a real 0.2.0 on main is "newer".
    assert update_check._is_newer("0.2.0", "0.2.0.dev0") is True


# ---------------------------------------------------------------------------
# check_for_update — end-to-end decision (network mocked)
# ---------------------------------------------------------------------------


def test_returns_latest_when_main_ahead(monkeypatch):
    monkeypatch.setattr(update_check, "__version__", "0.2.0")
    with patch.object(update_check, "fetch_main_version", return_value="0.3.0"):
        assert update_check.check_for_update() == "0.3.0"


def test_returns_none_when_up_to_date(monkeypatch):
    monkeypatch.setattr(update_check, "__version__", "0.2.0")
    with patch.object(update_check, "fetch_main_version", return_value="0.2.0"):
        assert update_check.check_for_update() is None


def test_returns_none_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(update_check, "__version__", "0.2.0")
    with patch.object(update_check, "fetch_main_version", return_value=None):
        assert update_check.check_for_update() is None


def test_opt_out_skips_network(monkeypatch):
    monkeypatch.setenv(update_check.OPT_OUT_ENV, "1")
    with patch.object(update_check, "fetch_main_version") as mock_fetch:
        assert update_check.check_for_update() is None
        mock_fetch.assert_not_called()


def test_cache_prevents_second_fetch(monkeypatch):
    monkeypatch.setattr(update_check, "__version__", "0.2.0")
    with patch.object(
        update_check, "fetch_main_version", return_value="0.3.0"
    ) as mock_fetch:
        assert update_check.check_for_update() == "0.3.0"
        assert update_check.check_for_update() == "0.3.0"
        mock_fetch.assert_called_once()  # second call served from the daily cache


# ---------------------------------------------------------------------------
# format_update_notice — points users at `shelley update`
# ---------------------------------------------------------------------------


def test_notice_points_at_shelley_update():
    notice = update_check.format_update_notice("9.9.9")
    assert "9.9.9" in notice
    assert "shelley update" in notice
