"""Verify that batch_build_modules is correctly wired after moving to utils.batch."""

import sys
from unittest.mock import patch

import pytest

from shelley.client.cli import main


def test_import_path_resolves(tmp_path, monkeypatch):
    """patch('shelley.client.cli.batch_build_modules') intercepts file-based build."""
    f = tmp_path / "tools.txt"
    f.write_text("samtools\n")
    monkeypatch.setattr(sys, "argv", ["shelley", "build", str(f)])

    with patch("shelley.client.cli.batch_build_modules", return_value=0) as mock_batch:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_batch.assert_called_once_with(["samtools"])
