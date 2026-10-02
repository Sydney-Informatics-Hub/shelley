"""Tests for verbose flag parsing and the build/path helper."""

from shelley.utils.args import parse_build_flags, parse_verbose
from shelley.utils.cache import compute_build_entries

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


# ---------------------------------------------------------------------------
# parse_build_flags
# ---------------------------------------------------------------------------


def test_build_flags_none():
    assert parse_build_flags(["samtools/1.21"]) == (False, ["samtools/1.21"])


def test_build_flags_interactive_long():
    assert parse_build_flags(["samtools/1.21", "--interactive"]) == (
        True,
        ["samtools/1.21"],
    )


def test_build_flags_interactive_short():
    assert parse_build_flags(["samtools/1.21", "-i"]) == (True, ["samtools/1.21"])


def test_build_flags_interactive_before_positional():
    assert parse_build_flags(["-i", "samtools/1.21"]) == (True, ["samtools/1.21"])


def test_stacked_long_flags():
    assert parse_verbose(["--verbose", "--verbose", "x"]) == (True, ["x"])


# ---------------------------------------------------------------------------
# compute_build_entries — one row per build, keeps paths and dates, no dedup,
# sorted by version (desc) then build date (desc)
# ---------------------------------------------------------------------------


def test_build_entries_keep_every_build_and_path():
    triples = [
        # A newer build of the older version must still sort below every 1.21 build.
        (
            "1.20--h50ea8bc_0",
            "/cvmfs/.../samtools:1.20--h50ea8bc_0",
            1700000000.0,
        ),  # 2023-11-14
        (
            "1.21--h50ea8bc_0",
            "/cvmfs/.../samtools:1.21--h50ea8bc_0",
            1564711787.0,
        ),  # 2019-08-02
        (
            "1.21--h96c455f_1",
            "/cvmfs/.../samtools:1.21--h96c455f_1",
            1564719341.0,
        ),  # 2019-08-02 (later)
    ]
    entries = compute_build_entries("samtools", triples)

    # No deduplication; ordered by version desc, then build date desc within a version.
    assert [e["tag"] for e in entries] == [
        "1.21--h96c455f_1",
        "1.21--h50ea8bc_0",
        "1.20--h50ea8bc_0",
    ]
    assert [e["path"] for e in entries] == [
        "/cvmfs/.../samtools:1.21--h96c455f_1",
        "/cvmfs/.../samtools:1.21--h50ea8bc_0",
        "/cvmfs/.../samtools:1.20--h50ea8bc_0",
    ]
    assert [e["date"] for e in entries] == ["2019-08-02", "2019-08-02", "2023-11-14"]
