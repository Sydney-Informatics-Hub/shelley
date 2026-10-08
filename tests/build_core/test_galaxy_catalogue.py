"""GalaxyCatalogue

The same assertions run against a fixture mount (always) and, where marked ``cvmfs``,
against the live Galaxy mount with the bundled snapshot.
"""

from pathlib import Path

import pytest

from shelley.errors import AmbiguousTag, MountUnavailable, TagNotFound, TagRequired
from shelley.galaxy.catalogue import GalaxyCatalogue
from shelley.tags import Tag

from .conftest import GOLDEN, MULLED, golden_entries


@pytest.fixture
def catalogue(galaxy_mount, galaxy_snapshot):
    entries = golden_entries()
    return GalaxyCatalogue(
        snapshot=galaxy_snapshot(entries), mount=galaxy_mount(entries)
    )


def test_tags_are_newest_first(catalogue):
    tags = catalogue.tags("samtools")
    assert [t.raw for t in tags] == [
        "1.21--h50ea8bc_3",
        "1.10--h2e538c0_3",
        "1.9--h91753b0_8",
    ]


def test_unknown_tool_has_no_tags(catalogue):
    assert catalogue.tags("no-such-tool") == []


@pytest.mark.parametrize("tool", sorted(GOLDEN))
def test_resolve_without_version_is_latest(catalogue, tool):
    assert catalogue.resolve(tool).raw == GOLDEN[tool][1]


def test_resolve_exact_tag(catalogue):
    assert catalogue.resolve("samtools", "1.10--h2e538c0_3").raw == "1.10--h2e538c0_3"


def test_resolve_version(catalogue):
    assert catalogue.resolve("samtools", "1.10").raw == "1.10--h2e538c0_3"


def test_resolve_never_prefix_matches(catalogue):
    with pytest.raises(TagNotFound) as exc:
        catalogue.resolve("samtools", "1.1")
    assert exc.value.available == ["1.21", "1.10", "1.9"]


def test_resolve_version_with_several_builds_is_ambiguous(catalogue):
    with pytest.raises(AmbiguousTag) as exc:
        catalogue.resolve("seqtk", "1.5")
    assert exc.value.matches == ["1.5--h577a1d6_1", "1.5--h577a1d6_0"]


def test_resolve_mulled_without_tag(catalogue):
    with pytest.raises(TagRequired):
        catalogue.resolve(MULLED[0])
    assert catalogue.resolve(MULLED[0], MULLED[1][0]).raw == MULLED[1][0]


def test_lookup_is_case_and_separator_insensitive(catalogue):
    assert catalogue.resolve("Integron-Finder").raw == "2.0.6--py_0"
    assert catalogue.name("INTEGRON-FINDER") == "integron_finder"


def test_both_spellings_stay_distinct_containers(catalogue):
    assert catalogue.resolve("t_coffee").raw == "11.0.8--py_0"
    assert catalogue.resolve("t-coffee").raw == "13.46.0--h1"


def test_new_tag_on_the_mount_resolves_through_the_live_fallback(
    galaxy_mount, galaxy_snapshot
):
    snapshot = galaxy_snapshot([("samtools", "1.21--h50ea8bc_3")])
    mount = galaxy_mount([("samtools", "1.21--h50ea8bc_3"), ("samtools", "1.22--h1")])
    cat = GalaxyCatalogue(snapshot=snapshot, mount=mount)
    assert cat.resolve("samtools").raw == "1.21--h50ea8bc_3"  # what find shows
    assert cat.resolve("samtools", "1.22").raw == "1.22--h1"  # by name, from the mount


def test_new_tool_on_the_mount_resolves(galaxy_mount, galaxy_snapshot):
    cat = GalaxyCatalogue(
        snapshot=galaxy_snapshot([]), mount=galaxy_mount([("newtool", "0.1--0")])
    )
    assert cat.resolve("newtool").raw == "0.1--0"


def test_unknown_tool_is_not_found(catalogue):
    with pytest.raises(TagNotFound):
        catalogue.resolve("no-such-tool")


def test_verify_returns_the_sif_path(catalogue):
    tag = catalogue.resolve("integron-finder")
    assert (
        catalogue.verify("integron-finder", tag).name == "integron_finder:2.0.6--py_0"
    )


def test_verify_detects_a_tag_missing_from_the_mount(galaxy_mount, galaxy_snapshot):
    cat = GalaxyCatalogue(
        snapshot=galaxy_snapshot([("samtools", "1.21--h1")]), mount=galaxy_mount([])
    )
    with pytest.raises(TagNotFound):
        cat.verify("samtools", Tag("1.21--h1"))


def test_verify_without_the_mount(galaxy_snapshot, tmp_path):
    cat = GalaxyCatalogue(
        snapshot=galaxy_snapshot([("samtools", "1.21--h1")]), mount=tmp_path / "absent"
    )
    assert cat.resolve("samtools").raw == "1.21--h1"  # the snapshot still answers
    with pytest.raises(MountUnavailable):
        cat.verify("samtools", Tag("1.21--h1"))


def test_live_fallback_without_the_mount(galaxy_snapshot, tmp_path):
    cat = GalaxyCatalogue(snapshot=galaxy_snapshot([]), mount=tmp_path / "absent")
    with pytest.raises(MountUnavailable):
        cat.resolve("samtools")


def test_default_mount_follows_the_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELLEY_CVMFS_PATH", str(tmp_path))
    assert GalaxyCatalogue().mount == Path(tmp_path)


@pytest.mark.cvmfs
def test_live_mount_contract():
    """The bundled snapshot and the live mount agree for a well-known tool."""
    cat = GalaxyCatalogue(mount=Path("/cvmfs/singularity.galaxyproject.org/all"))
    tag = cat.resolve("samtools")
    assert cat.verify("samtools", tag).exists()
    assert tag == max(cat.tags("samtools"))
