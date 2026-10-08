import pytest

import shelley.galaxy.exposer as exposer_mod
from shelley.errors import NetworkUnavailable
from shelley.galaxy.exposer import ShpcExposer
from shelley.galaxy.registry import LOCAL_TAG_VALUE, LocalRegistry, Marker
from shelley.tags import Tag
from shelley.tools.lmod import Lmod
from shelley.utils import globals as gl

from .fakes import UPSTREAM_SAMTOOLS, FakeRegistry, FakeShpc
from .tree import changes, snapshot

URI = "quay.io/biocontainers/samtools"
UP = Tag("1.21--h50ea8bc_3")  # in upstream
LOCAL = Tag("1.19--h1")  # not in upstream


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
        registry=FakeRegistry({URI: UPSTREAM_SAMTOOLS}, reachable=reachable),
        shpc=shpc or FakeShpc(),
        discover=discover,
    )
    exp.discover_calls = calls
    return exp


def build(exp, tag, sif, curate=None):
    return exp.apply(exp.plan("samtools", tag, sif, curate=curate))


# ------------------------------------------------------------------ plans
def test_upstream_tag_needs_no_local_entry(sif):
    plan = make().plan("samtools", UP, sif)
    assert plan.in_upstream and plan.local_entry is None and plan.marker is None
    assert plan.aliases == [{"name": "samtools", "command": "/usr/local/bin/samtools"}]


def test_tag_absent_upstream_gets_a_local_entry_with_discovered_aliases(sif):
    exp = make(discovered=[{"name": "samtools", "command": "samtools"}])
    plan = exp.plan("samtools", LOCAL, sif)
    assert not plan.in_upstream
    assert plan.local_entry["tags"][LOCAL.raw] == LOCAL_TAG_VALUE
    assert UP.raw in plan.local_entry["tags"]  # upstream tags kept: no shadowing
    assert plan.marker == Marker(LOCAL.raw, plan.aliases, in_upstream=False)
    assert exp.discover_calls == [(sif, "samtools")]


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
