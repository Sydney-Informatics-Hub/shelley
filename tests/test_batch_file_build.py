"""Tests for reading a tools file for `shelley build`."""

import pytest

from shelley.client.build import read_tools_file as _read_tools_file

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
