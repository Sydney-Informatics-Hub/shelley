"""Tag: one ordering rule for every command (ADR 0002)."""

import gzip
import json
import random

import pytest

from shelley.errors import TagRequired
from shelley.tags import Tag, latest, newest_first
from shelley.utils.globals import DATA_DIR

from .conftest import GOLDEN, MULLED


@pytest.mark.parametrize("tool", sorted(GOLDEN))
def test_latest_golden(tool):
    tags, expected = GOLDEN[tool]
    assert latest(tool, [Tag(t) for t in tags]).raw == expected


def test_mulled_requires_a_tag():
    with pytest.raises(TagRequired) as exc:
        latest(MULLED[0], [Tag(t) for t in MULLED[1]])
    assert exc.value.available == sorted(MULLED[1], reverse=True)


def test_latest_of_nothing_is_an_error():
    with pytest.raises(ValueError):
        latest("samtools", [])


@pytest.mark.parametrize(
    ("raw", "version", "build"),
    [
        ("1.21--h50ea8bc_3", "1.21", "h50ea8bc_3"),
        ("1.4.1", "1.4.1", None),
        ("v1.0--0", "1.0", "0"),
        ("v.1.1.0--r1", "1.1.0", "r1"),
        ("vcf2maf", "vcf2maf", None),  # a leading v that is not a version prefix stays
    ],
)
def test_version_and_build(raw, version, build):
    tag = Tag(raw)
    assert (tag.version, tag.build) == (version, build)


def test_matches_exact_tag_or_version_never_prefix():
    tag = Tag("1.10--h2e538c0_3")
    assert tag.matches("1.10--h2e538c0_3")
    assert tag.matches("1.10")
    assert not tag.matches("1.1")  # T4: prefix matching made 1.1 look installed
    assert not tag.matches("1")
    assert Tag("v1.0--0").matches("1.0") and Tag("1.0--0").matches("v1.0")


@pytest.mark.parametrize(
    "raw",
    [
        "latest--0",
        "broken--0",
        "date.2011_11_26--0",
        "_1.1--py27_0",
    ],  # last: conda cannot parse it
)
def test_non_versions_are_not_releases(raw):
    assert not Tag(raw).is_release


def test_non_versions_sort_below_any_release():
    assert Tag("latest--0") < Tag("0.0.1--0")
    assert newest_first([Tag("broken--0"), Tag("0.1--0")])[0].raw == "0.1--0"


def test_newest_build_wins_within_a_version():
    assert max(Tag("1.5--h577a1d6_0"), Tag("1.5--h577a1d6_1")).raw == "1.5--h577a1d6_1"


def test_equality_is_by_full_tag():
    assert Tag("1.0--0") == Tag("1.0--0")
    assert Tag("1.0--0") != Tag("1.0--1")
    assert Tag("1.0--0").same_version(Tag("v1.0--3"))
    assert len({Tag("1.0--0"), Tag("1.0--0")}) == 1


def test_ordering_is_a_strict_total_order_on_real_tags():
    """Antisymmetry and transitivity over a sample of the bundled Galaxy snapshot."""
    with gzip.open(DATA_DIR / "galaxy_singularity_cache.json.gz", "rt") as f:
        raws = sorted({e["tag"] for e in json.load(f)["entries"] if e["tag"]})
    sample = [Tag(t) for t in random.Random(7).sample(raws, 150)]
    for a in sample:
        assert not a < a
        for b in sample:
            if a != b:
                assert (a < b) != (b < a), (a, b)
    ordered = sorted(sample)
    assert all(not ordered[i + 1] < ordered[i] for i in range(len(ordered) - 1))
