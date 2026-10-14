"""Tests for verbose flag parsing and the build/path helper."""

from shelley.utils.args import parse_force_flag, parse_verbose

# ---------------------------------------------------------------------------
# parse_verbose
# ---------------------------------------------------------------------------


def test_no_flags():
    assert parse_verbose(["samtools"]) == (False, ["samtools"])


def test_single_short_flag():
    assert parse_verbose(["samtools", "-v"]) == (True, ["samtools"])


def test_long_flag():
    assert parse_verbose(["--verbose", "samtools"]) == (True, ["samtools"])


def test_double_short_flag():
    assert parse_verbose(["-vv", "samtools"]) == (True, ["samtools"])


def test_stacked_short_flags():
    assert parse_verbose(["-v", "samtools", "-v"]) == (True, ["samtools"])


def test_stacked_long_flags():
    assert parse_verbose(["--verbose", "--verbose", "x"]) == (True, ["x"])


def test_force_flag():
    assert parse_force_flag(["samtools:1.21", "-y"]) == (True, ["samtools:1.21"])


def test_no_force_flag():
    assert parse_force_flag(["samtools:1.21"]) == (False, ["samtools:1.21"])
