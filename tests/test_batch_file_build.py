"""Tests for file-input dispatch in `shelley build`."""

import sys
from unittest.mock import patch

import pytest

from shelley.client.cli import main
from shelley.utils.batch import read_tools_file as _read_tools_file

# ---------------------------------------------------------------------------
# _read_tools_file unit tests
# ---------------------------------------------------------------------------


def test_read_normal(tmp_path):
    f = tmp_path / "tools.txt"
    f.write_text("samtools\nfastqc\nbowtie2\n")
    assert _read_tools_file(f) == ["samtools", "fastqc", "bowtie2"]


def test_read_strips_comments_and_blanks(tmp_path):
    f = tmp_path / "tools.txt"
    f.write_text(
        "# header\nsamtools\n\nfastqc  # pinned\n  # inline-only line\nbowtie2\n"
    )
    assert _read_tools_file(f) == ["samtools", "fastqc", "bowtie2"]


def test_read_all_comments_returns_empty(tmp_path):
    f = tmp_path / "tools.txt"
    f.write_text("# nothing here\n# another comment\n\n\n")
    assert _read_tools_file(f) == []


def test_read_inline_comment_stripped(tmp_path):
    f = tmp_path / "tools.txt"
    f.write_text("samtools/1.21  # latest stable\n")
    assert _read_tools_file(f) == ["samtools/1.21"]


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _read_tools_file(tmp_path / "nonexistent.txt")


# ---------------------------------------------------------------------------
# main() dispatch tests
# ---------------------------------------------------------------------------


def test_main_file_arg_calls_batch(tmp_path, monkeypatch):
    """File arg → batch_build_modules called with parsed tools; build_module not called."""
    f = tmp_path / "tools.txt"
    f.write_text("samtools\nfastqc\n")
    monkeypatch.setattr(sys, "argv", ["shelley", "build", str(f)])

    with (
        patch("shelley.client.cli.batch_build_modules", return_value=0) as mock_batch,
        patch("shelley.client.cli.build_module") as mock_single,
    ):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_batch.assert_called_once_with(["samtools", "fastqc"])
        mock_single.assert_not_called()


def test_main_non_file_arg_calls_single(monkeypatch):
    """Non-file arg → build_module called unchanged; batch_build_modules not called."""
    monkeypatch.setattr(sys, "argv", ["shelley", "build", "samtools"])

    with (
        patch("shelley.client.cli.build_module", return_value=True) as mock_single,
        patch("shelley.client.cli.batch_build_modules") as mock_batch,
    ):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_single.assert_called_once_with("samtools", interactive=False)
        mock_batch.assert_not_called()


def test_main_empty_file_exits_1_with_warning(tmp_path, monkeypatch):
    """All-comment file → exit 1, warning printed, neither build function called."""
    f = tmp_path / "tools.txt"
    f.write_text("# nothing\n\n")
    monkeypatch.setattr(sys, "argv", ["shelley", "build", str(f)])

    with (
        patch("shelley.client.cli.batch_build_modules") as mock_batch,
        patch("shelley.client.cli.build_module") as mock_single,
        patch("shelley.client.cli.print_warning") as mock_warn,
    ):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        mock_batch.assert_not_called()
        mock_single.assert_not_called()
        mock_warn.assert_called_once()


def test_main_batch_failure_propagates_exit_code(tmp_path, monkeypatch):
    """batch_build_modules returning 1 → main exits 1."""
    f = tmp_path / "tools.txt"
    f.write_text("samtools\n")
    monkeypatch.setattr(sys, "argv", ["shelley", "build", str(f)])

    with patch("shelley.client.cli.batch_build_modules", return_value=1):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
