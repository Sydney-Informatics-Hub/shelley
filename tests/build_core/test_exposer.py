import pytest

import shelley.galaxy.exposer as exposer_mod
from shelley.errors import NetworkUnavailable
from shelley.galaxy.exposer import ShpcExposer
from shelley.galaxy.registry import LOCAL_TAG_VALUE, LocalRegistry, Marker
from shelley.tags import Tag
from shelley.tools.lmod import Lmod
from shelley.utils import globals as gl

from .fakes import UPSTREAM_SAMTOOLS, FakeRegistry, FakeShpc
from .roots_snapshot import changes, snapshot

URI = "quay.io/biocontainers/samtools"
UP = Tag("1.21--h50ea8bc_3")  # in upstream
LOCAL = Tag("1.19--h1")  # not in upstream
UPSTREAM = {
    URI: UPSTREAM_SAMTOOLS,
    "quay.io/biocontainers/bcftools": {
        "tags": {"1.23.1--hb2cee57_0": "sha256:a"},
        "aliases": {
            "bcftools": "/usr/local/bin/bcftools",
            "bgzip": "/usr/local/bin/bgzip",
            "tabix": "/usr/local/bin/tabix",
        },
    },
    "quay.io/biocontainers/vcftools": {
        "tags": {"0.1.17--pl5321h077b44d_0": "sha256:b"},
        "aliases": {"vcftools": "/usr/local/bin/vcftools"},
    },
    "quay.io/biocontainers/star": {
        "tags": {"2.7.11a--h0033a41_0": "sha256:c"},
        "aliases": {"STAR": "/usr/local/bin/STAR"},
    },
    "quay.io/biocontainers/bwa-mem2": {
        "tags": {"2.2.1--he70b90d_8": "sha256:d"},
        "aliases": {"bwa-mem2": "/usr/local/bin/bwa-mem2"},
    },
}


def roots():
    return [gl.shpc_base(), gl.local_registry(), gl.lmod_modules()]


@pytest.fixture
def sif(tmp_path):
    path = tmp_path / "samtools.sif"
    path.touch()
    return path


def make(shpc=None, reachable=True, discovered=None):
    found = [] if discovered is None else discovered
    calls = []

    def discover(sif, keep=None):
        calls.append((sif, keep))
        return list(found)

    exp = ShpcExposer(
        registry=FakeRegistry(dict(UPSTREAM), reachable=reachable),
        shpc=shpc or FakeShpc(),
        discover=discover,
    )
    exp.discover_calls = calls
    return exp


def build(exp, tag, sif, curate=None):
    return exp.apply(exp.plan("samtools", tag, sif, curate=curate))


# ------------------------------------------------------------------ plans
@pytest.mark.parametrize(
    ("tool", "tag", "aliases"),
    [
        (
            "samtools",
            UP.raw,
            [{"name": "samtools", "command": "/usr/local/bin/samtools"}],
        ),
        (
            "bcftools",
            "1.23.1--hb2cee57_0",
            [
                {"name": "bcftools", "command": "/usr/local/bin/bcftools"},
                {"name": "bgzip", "command": "/usr/local/bin/bgzip"},
                {"name": "tabix", "command": "/usr/local/bin/tabix"},
            ],
        ),
        (
            "vcftools",
            "0.1.17--pl5321h077b44d_0",
            [{"name": "vcftools", "command": "/usr/local/bin/vcftools"}],
        ),
        (
            "star",
            "2.7.11a--h0033a41_0",
            [{"name": "STAR", "command": "/usr/local/bin/STAR"}],
        ),
    ],
)
def test_upstream_tag_needs_no_local_entry(sif, tool, tag, aliases):
    plan = make().plan(tool, Tag(tag), sif)
    assert plan.in_upstream and plan.local_entry is None and plan.marker is None
    assert plan.aliases == aliases


@pytest.mark.parametrize(
    ("tool", "tag", "upstream_tag"),
    [
        ("samtools", LOCAL.raw, UP.raw),
        ("bcftools", "1.6--1", "1.23.1--hb2cee57_0"),
        ("vcftools", "0.1.12b--pl5262h2e03b76_2", "0.1.17--pl5321h077b44d_0"),
        (
            "bwa-mem2",
            "2.2.1--hd03093a_5",
            "2.2.1--he70b90d_8",
        ),  # same version, other build
    ],
)
def test_tag_absent_upstream_gets_a_local_entry_with_discovered_aliases(
    sif, tool, tag, upstream_tag
):
    exp = make(discovered=[{"name": tool, "command": tool}])
    plan = exp.plan(tool, Tag(tag), sif)
    assert not plan.in_upstream
    assert plan.local_entry["tags"][tag] == LOCAL_TAG_VALUE
    assert upstream_tag in plan.local_entry["tags"]  # upstream tags kept: no shadowing
    assert plan.marker == Marker(tag, plan.aliases, in_upstream=False)
    assert exp.discover_calls == [(sif, tool)]


def test_curated_upstream_tag_is_marked_in_upstream(sif):
    curated = [{"name": "st", "command": "samtools"}]
    plan = make().plan("samtools", UP, sif, curate=lambda aliases: curated)
    assert plan.local_entry["aliases"] == curated
    assert plan.marker.in_upstream is True


def test_plan_writes_nothing(sif):
    before = snapshot(*roots())
    make(discovered=[{"name": "x", "command": "x"}]).plan("samtools", LOCAL, sif)
    assert changes(before, snapshot(*roots())) == []


def test_offline_plan_stops_before_writing(sif):
    """Port of spike B: no network must never read as "not upstream" (T6)."""
    before = snapshot(*roots())
    with pytest.raises(NetworkUnavailable, match="Couldn't reach GitHub"):
        make(reachable=False).plan("samtools", UP, sif)
    assert changes(before, snapshot(*roots())) == []


def test_alias_discovery_offline_stops_before_writing(sif):
    exp = make()

    def unreachable(sif, keep=None):
        raise NetworkUnavailable("github.com", "the name could not be resolved")

    exp.discover = unreachable
    before = snapshot(*roots())
    with pytest.raises(NetworkUnavailable):
        exp.plan("samtools", LOCAL, sif)
    assert changes(before, snapshot(*roots())) == []


# ------------------------------------------------------------------ apply
def test_build_links_a_loadable_module(sif):
    link = build(make(), UP, sif)
    assert link == gl.lmod_modules() / "samtools" / f"{UP.raw}.lua"
    assert link.resolve() == gl.shpc_module_base() / URI / UP.raw / "module.lua"
    assert link.is_file()
    assert LocalRegistry().read(URI) is None


def test_build_never_reads_the_sif(tmp_path):
    """No full-SIF hash any more (ADR 0006): a path that does not exist is fine."""
    build(make(), UP, tmp_path / "not-there.sif")


def test_cancelled_curation_keeps_the_installed_module(sif):
    """Port of spike A (T5): cancelling -i on an installed tag deletes nothing."""
    exp = make()
    link = build(exp, UP, sif)
    before = snapshot(*roots())

    def cancel(aliases):
        raise ValueError("Alias selection cancelled.")

    with pytest.raises(ValueError):
        exp.plan("samtools", UP, sif, curate=cancel)
    assert changes(before, snapshot(*roots())) == []
    assert link.is_file()


def test_rebuild_replaces_the_install_and_leaves_no_aside_copies(sif):
    exp = make()
    build(exp, UP, sif)
    plan = exp.plan("samtools", UP, sif)
    assert plan.replace_existing
    exp.apply(plan)
    leftovers = [p for root in roots() for p in root.rglob("*.aside")]
    assert leftovers == []


FAILURES = ["write", "install", "harden", "link"]


def _inject(step, monkeypatch, exp):
    def boom(*args, **kwargs):
        raise RuntimeError(f"injected after {step}")

    if step == "write":
        original = LocalRegistry.write

        def write_then_fail(self, *args, **kwargs):
            original(self, *args, **kwargs)
            boom()

        monkeypatch.setattr(LocalRegistry, "write", write_then_fail)
    elif step == "install":
        exp.shpc.fail_on = "install"
    elif step == "harden":
        monkeypatch.setattr(exposer_mod, "harden_tree", boom)
    elif step == "link":
        original = Lmod.link

        def link_then_fail(self, *args, **kwargs):
            original(self, *args, **kwargs)
            boom()

        monkeypatch.setattr(Lmod, "link", link_then_fail)


@pytest.mark.parametrize("step", FAILURES)
@pytest.mark.parametrize("scenario", ["fresh", "second-tag", "rebuild"])
def test_failure_at_any_step_leaves_apps_unchanged(step, scenario, sif, monkeypatch):
    exp = make(discovered=[{"name": "samtools", "command": "samtools"}])
    if scenario == "second-tag":
        build(exp, Tag("1.10--h2e538c0_3"), sif)
    elif scenario == "rebuild":
        build(exp, LOCAL, sif)
    # A local-entry build so the "write" step happens in every scenario.
    tag = LOCAL if scenario != "second-tag" else Tag("1.18--h9")
    plan = exp.plan("samtools", tag, sif)
    before = snapshot(*roots())
    _inject(step, monkeypatch, exp)
    with pytest.raises(Exception, match="injected|failed"):
        exp.apply(plan)
    assert changes(before, snapshot(*roots())) == []
    if scenario == "rebuild":
        assert (gl.lmod_modules() / "samtools" / f"{LOCAL.raw}.lua").is_file()


# ------------------------------------------------------------------ legacy entries
def test_legacy_entry_is_removed_by_the_next_build(sif):
    """Like star-fusion on the dev VM: upstream-looking, no marker, nothing linked."""
    LocalRegistry().write(
        URI, {"tags": {"1.0.0--pl5": "sha256:x"}, "maintainer": "@vsoch"}
    )
    exp = make()
    plan = exp.plan("samtools", UP, sif)
    assert plan.remove_legacy and plan.local_entry is None
    exp.apply(plan)
    assert LocalRegistry().read(URI) is None


def test_curated_entry_in_use_gets_newer_upstream_tags(sif):
    exp = make()
    curated = [{"name": "st", "command": "samtools"}]
    build(exp, Tag("1.10--h2e538c0_3"), sif, curate=lambda a: curated)
    exp.registry.entries[URI] = {
        **UPSTREAM_SAMTOOLS,
        "tags": {**UPSTREAM_SAMTOOLS["tags"], "1.22--h1": "sha256:ccc"},
    }
    plan = exp.plan("samtools", Tag("1.22--h1"), sif)
    assert not plan.remove_legacy
    assert "1.22--h1" in plan.local_entry["tags"]  # no stale shadow
    assert plan.aliases == curated  # shpc will use the local entry's aliases
    exp.apply(plan)
    assert "1.22--h1" in LocalRegistry().read(URI)["tags"]
