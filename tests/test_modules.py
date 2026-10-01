#!/usr/bin/env python3
"""pytest coverage for shelley.utils.modules.load_build_modules."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import shelley.utils.modules as modules
from shelley.utils.modules import load_build_modules


@pytest.fixture(autouse=True)
def reset_loaded():
    """Reset the warn-once/load-once guard between tests."""
    modules._LOADED = False
    yield
    modules._LOADED = False


def test_no_module_system_warns_and_continues(monkeypatch):
    """With no Lmod driver, load returns False and does not raise."""
    monkeypatch.delenv("LMOD_CMD", raising=False)
    with patch.object(modules.shutil, "which", return_value=None):
        assert load_build_modules(["shpc", "singularity"]) is False


def test_successful_load_mutates_environ(monkeypatch):
    """Lmod python output is exec'd, mutating os.environ."""
    monkeypatch.setenv("LMOD_CMD", "/fake/lmod")
    fake = MagicMock(
        returncode=0, stdout="os.environ['SHELLEY_TEST_LOADED'] = '1'\n", stderr=""
    )
    with patch.object(modules.subprocess, "run", return_value=fake) as run:
        os.environ.pop("SHELLEY_TEST_LOADED", None)
        assert load_build_modules(["shpc", "singularity"]) is True
        assert os.environ.get("SHELLEY_TEST_LOADED") == "1"
        run.assert_called_once_with(
            ["/fake/lmod", "python", "load", "shpc", "singularity"],
            capture_output=True,
            text=True,
        )
    os.environ.pop("SHELLEY_TEST_LOADED", None)


def test_failed_load_warns_and_continues(monkeypatch):
    """A non-zero Lmod return code warns and returns False without raising."""
    monkeypatch.setenv("LMOD_CMD", "/fake/lmod")
    fake = MagicMock(returncode=1, stdout="", stderr="module not found")
    with patch.object(modules.subprocess, "run", return_value=fake):
        assert load_build_modules(["shpc"]) is False


def test_load_is_idempotent(monkeypatch):
    """A second call short-circuits without invoking Lmod again."""
    monkeypatch.setenv("LMOD_CMD", "/fake/lmod")
    fake = MagicMock(returncode=0, stdout="", stderr="")
    with patch.object(modules.subprocess, "run", return_value=fake) as run:
        assert load_build_modules(["shpc"]) is True
        assert load_build_modules(["shpc"]) is True
        run.assert_called_once()
