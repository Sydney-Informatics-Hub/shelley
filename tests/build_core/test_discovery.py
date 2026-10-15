"""find, search and clean on the new core (migration plan batch 4)."""

import sys

import pytest

import shelley.client.discovery as discovery
from shelley import privilege, services
from shelley.errors import AmbiguousTag
from shelley.galaxy.catalogue import GalaxyCatalogue
from shelley.galaxy.exposer import ShpcExposer
from shelley.galaxy.registry import LocalRegistry
from shelley.results import TagState
from shelley.search.base import MetadataSource
from shelley.tags import Tag
from shelley.tools.lmod import Lmod
from shelley.tools.shpc import ShpcFailed
from shelley.utils import globals as gl

from .conftest import MULLED, golden_entries
from .fakes import UPSTREAM_SAMTOOLS, FakeRegistry, FakeShpc
from .roots_snapshot import changes, snapshot


class Source(MetadataSource):
    """Metadata with injected entries (the real RSEC search algorithm)."""

    def __init__(self, entries):
        super().__init__()
        self.entries = list(entries)

    def search(self, query, limit=None):
        q = query.lower()
        return sorted(
            e["name"] for e in self.entries if q in (e.get("description") or "").lower()
        )


SAMTOOLS_META = {
    "id": "samtools",
    "name": "SAMtools",
    "description": "Utilities for SAM/BAM alignment files",
    "homepage": "http://www.htslib.org",
    "edam-operations": ["Read mapping"],
}


def roots():
    return [gl.shpc_base(), gl.local_registry(), gl.lmod_modules()]


@pytest.fixture
def catalogue(galaxy_mount, galaxy_snapshot):
    entries = golden_entries()
    return GalaxyCatalogue(
        snapshot=galaxy_snapshot(entries), mount=galaxy_mount(entries)
    )


def link(tool, tag, target_exists=True):
    """A modulefile link as a build leaves it; dangling if its target is gone."""
    tool_dir = gl.lmod_modules() / tool
    tool_dir.mkdir(parents=True, exist_ok=True)
    target = gl.shpc_module_base() / "quay.io/biocontainers" / tool / tag / "module.lua"
    if target_exists:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("--\n")
    (tool_dir / f"{tag}.lua").symlink_to(target)


# ------------------------------------------------------------------ catalogue
def test_installed_reports_linked_and_dangling(catalogue):
    link("samtools", "1.10--h2e538c0_3")
    link("samtools", "1.9--h91753b0_8", target_exists=False)
    assert catalogue.installed("samtools") == {
        Tag("1.10--h2e538c0_3"): TagState.LINKED,
        Tag("1.9--h91753b0_8"): TagState.DANGLING,
    }


def test_builds_keep_paths_and_dates_newest_first(catalogue):
    builds = catalogue.builds("samtools")
    assert [b.tag.raw for b in builds] == [
        "1.21--h50ea8bc_3",
        "1.10--h2e538c0_3",
        "1.9--h91753b0_8",
    ]
    assert builds[0].path.name == "samtools:1.21--h50ea8bc_3"


# ------------------------------------------------------------------ find
def test_find_top_row_is_what_build_installs(catalogue):
    result = services.find("samtools", catalogue, Source([SAMTOOLS_META]))
    assert result.versions[0].version == result.latest.version == "1.21"
    assert result.latest == catalogue.resolve("samtools")
    assert result.meta.operations == ("Read mapping",)


def test_find_installed_ticks_match_exactly(catalogue):
    """T4: 1.10 installed must not tick 1.1 or 1 (0.4.0 used a prefix glob)."""
    link("samtools", "1.10--h2e538c0_3")
    result = services.find("samtools", catalogue, Source([]))
    ticks = {row.version: row.installed for row in result.versions}
    assert ticks == {"1.21": False, "1.10": True, "1.9": False}


def test_find_dangling_link_is_not_installed(catalogue):
    link("samtools", "1.10--h2e538c0_3", target_exists=False)
    result = services.find("samtools", catalogue, Source([]))
    assert not any(row.installed for row in result.versions)


def test_find_verbose_lists_every_build_with_its_state(catalogue):
    link("seqtk", "1.5--h577a1d6_0")
    result = services.find("seqtk", catalogue, Source([]), verbose=True)
    states = {b.tag.raw: s for b, s in result.builds}
    assert states["1.5--h577a1d6_0"] is TagState.LINKED
    assert states["1.5--h577a1d6_1"] is None


def test_find_mulled_has_no_latest(catalogue):
    assert services.find(MULLED[0], catalogue, Source([])).latest is None


def test_find_strips_a_version_from_the_query(catalogue):
    assert services.find("samtools/1.21", catalogue, Source([])).tool == "samtools"


def test_find_unknown_tool_suggests_close_names(catalogue):
    result = services.find("samtool", catalogue, Source([SAMTOOLS_META]))
    assert not result.found
    assert result.suggestions == (("SAMtools", SAMTOOLS_META["description"]),)


def test_find_metadata_without_containers(catalogue):
    meta = {"id": "seurat", "name": "Seurat", "description": "single-cell"}
    result = services.find("seurat", catalogue, Source([meta]))
    assert result.found and result.tool is None and result.versions == ()


def test_find_and_build_agree_for_every_tool_in_the_real_snapshot(tmp_path):
    """T1 closed: over the bundled snapshot, find's top row is build's default."""
    catalogue = GalaxyCatalogue(mount=tmp_path, lmod_dir=tmp_path)
    source = Source([])
    disagree = []
    for tool in catalogue.tool_ids():
        if tool.startswith("mulled-"):
            continue
        result = services.find(tool, catalogue, source)
        if result.versions and result.versions[0].version != result.latest.version:
            disagree.append(tool)
    assert disagree == []


# ------------------------------------------------------------------ search
def test_search_returns_only_tools_with_a_container(catalogue):
    entries = [
        SAMTOOLS_META,
        {"id": "seurat", "name": "Seurat", "description": "alignment-free"},
        {"id": "integron-finder", "name": "IntegronFinder", "description": "alignment"},
    ]
    results = services.search("alignment", Source(entries), catalogue)
    assert [name for name, _ in results] == ["IntegronFinder", "SAMtools"]


# ------------------------------------------------------------------ clean
def test_clean_requires_an_explicit_version(catalogue):
    link("samtools", "1.10--h2e538c0_3")
    with pytest.raises(services.NotInstalled) as exc:
        services.resolve_installed("samtools", catalogue)
    assert exc.value.installed == ["1.10--h2e538c0_3"]


def test_clean_matches_exact_tag_or_version_only(catalogue):
    link("samtools", "1.10--h2e538c0_3")
    assert (
        services.resolve_installed("samtools:1.10", catalogue)[1].raw
        == "1.10--h2e538c0_3"
    )
    with pytest.raises(services.NotInstalled):
        services.resolve_installed("samtools:1.1", catalogue)


def test_clean_ambiguous_version(catalogue):
    link("seqtk", "1.5--h577a1d6_0")
    link("seqtk", "1.5--h577a1d6_1")
    with pytest.raises(AmbiguousTag):
        services.resolve_installed("seqtk/1.5", catalogue)


def make_exposer(shpc=None):
    return ShpcExposer(
        registry=FakeRegistry({"quay.io/biocontainers/samtools": UPSTREAM_SAMTOOLS}),
        shpc=shpc or FakeShpc(),
        discover=lambda sif, keep=None: [{"name": "samtools", "command": "samtools"}],
    )


def build(exposer, tag, tmp_path):
    sif = tmp_path / f"samtools:{tag.raw}"
    sif.touch()
    exposer.apply(exposer.plan("samtools", tag, sif))


def test_build_then_clean_leaves_no_trace(tmp_path):
    """No orphans: clean is the exact inverse of a build, leftovers included."""
    exposer = make_exposer()
    before = snapshot(*roots())
    build(exposer, Tag("1.19--h1"), tmp_path)  # not upstream: local entry + marker
    result = exposer.remove("samtools", Tag("1.19--h1"))
    assert changes(before, snapshot(*roots())) == []
    assert "local registry entry (last installed version)" in result.removed


def test_clean_one_of_two_versions_keeps_the_other(tmp_path):
    exposer = make_exposer()
    build(exposer, Tag("1.19--h1"), tmp_path)
    build(exposer, Tag("1.21--h50ea8bc_3"), tmp_path)
    exposer.remove("samtools", Tag("1.19--h1"))
    uri = "quay.io/biocontainers/samtools"
    assert not (gl.shpc_wrapper_base() / uri / "1.19--h1").exists()  # no orphan wrapper
    assert (gl.lmod_modules() / "samtools" / "1.21--h50ea8bc_3.lua").is_file()
    entry = LocalRegistry().read(uri)
    assert entry is None or "1.19--h1" not in entry.get("tags", {})
    assert "1.19--h1" not in LocalRegistry().markers(uri)


def test_clean_keeps_a_curated_tag_that_is_still_upstream(tmp_path):
    """Its marker goes, but the tag stays in the entry: upstream still has it."""
    exposer = make_exposer()
    up = Tag("1.21--h50ea8bc_3")
    sif = tmp_path / f"samtools:{up.raw}"
    sif.touch()
    curated = [{"name": "st", "command": "samtools"}]
    exposer.apply(exposer.plan("samtools", up, sif, curate=lambda aliases: curated))
    build(exposer, Tag("1.19--h1"), tmp_path)  # keeps the tool installed
    uri = "quay.io/biocontainers/samtools"
    assert LocalRegistry().markers(uri)[up.raw].in_upstream is True

    exposer.remove("samtools", up)

    assert up.raw not in LocalRegistry().markers(uri)
    assert up.raw in LocalRegistry().read(uri)["tags"]
    assert not (gl.lmod_modules() / "samtools" / f"{up.raw}.lua").exists()


def test_failed_shpc_uninstall_changes_nothing(tmp_path):
    exposer = make_exposer()
    build(exposer, Tag("1.21--h50ea8bc_3"), tmp_path)
    exposer.shpc.fail_on = "uninstall"
    before = snapshot(*roots())
    with pytest.raises(ShpcFailed):
        exposer.remove("samtools", Tag("1.21--h50ea8bc_3"))
    assert changes(before, snapshot(*roots())) == []


def test_clean_resolved_validates_and_checks_installed(catalogue):
    with pytest.raises(services.InvalidSpec):
        services.clean_resolved("../etc:x", catalogue, make_exposer())
    with pytest.raises(services.NotInstalled):
        services.clean_resolved("samtools:1.21--h50ea8bc_3", catalogue, make_exposer())


# ------------------------------------------------------------------ CLI
@pytest.fixture
def cli_catalogue(catalogue, monkeypatch):
    monkeypatch.setattr(discovery, "GalaxyCatalogue", lambda: catalogue)
    return catalogue


@pytest.fixture
def sudo(monkeypatch):
    calls = []
    monkeypatch.setattr(privilege, "needs_root", lambda: True)
    monkeypatch.setattr(privilege, "reexec", lambda args: calls.append(args) or 0)
    return calls


def test_clean_not_installed_is_reported_before_sudo(cli_catalogue, sudo):
    assert discovery.run_clean(["samtools:1.21", "-y"]) == 1
    assert sudo == []


def test_clean_reexecs_once_with_the_resolved_tag(cli_catalogue, sudo):
    link("samtools", "1.10--h2e538c0_3")
    assert discovery.run_clean(["samtools:1.10", "-y"]) == 0
    assert sudo == [["clean", "--resolved-tag", "samtools:1.10--h2e538c0_3", "-y"]]


def test_clean_declined_confirmation_removes_nothing(cli_catalogue, sudo, monkeypatch):
    link("samtools", "1.10--h2e538c0_3")
    monkeypatch.setattr(discovery, "_confirm", lambda tool, tag: False)
    assert discovery.run_clean(["samtools:1.10"]) == 1
    assert sudo == []


def test_clean_root_child_removes_the_tag(cli_catalogue, tmp_path, monkeypatch):
    exposer = make_exposer()
    build(exposer, Tag("1.21--h50ea8bc_3"), tmp_path)
    monkeypatch.setattr(privilege, "needs_root", lambda: False)
    monkeypatch.setattr(Lmod, "load_build_modules", lambda self: True)
    monkeypatch.setattr(discovery, "ShpcExposer", lambda lmod: exposer)
    code = discovery.run_clean(["--resolved-tag", "samtools:1.21--h50ea8bc_3", "-y"])
    assert code == 0
    assert not (gl.lmod_modules() / "samtools").exists()


@pytest.mark.parametrize("leftover", [{}, {"SHELLEY_NEW_DISCOVERY": "1"}])
@pytest.mark.parametrize("command", ["find", "search", "clean"])
def test_cli_routes_every_discovery_command_to_the_core(command, leftover, monkeypatch):
    """One route: a leftover ``SHELLEY_NEW_DISCOVERY`` changes nothing."""
    from shelley.client import cli

    seen = []
    for k, v in leftover.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cli, f"run_{command}", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["shelley", command, "samtools"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0 and seen == [["samtools"]]


@pytest.mark.parametrize("command", ["find", "search", "clean"])
def test_cli_passes_the_exit_code_through(command, monkeypatch):
    from shelley.client import cli

    monkeypatch.setattr(cli, f"run_{command}", lambda argv: 1)
    monkeypatch.setattr(sys, "argv", ["shelley", command])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1


@pytest.mark.parametrize("runner", ["run_find", "run_search", "run_clean"])
def test_missing_arguments_print_usage_and_exit_1(runner, capsys, monkeypatch):
    # clean constructs its catalogue before parsing; find and search must not look up
    unused = (
        (lambda: None) if runner == "run_clean" else (lambda: pytest.fail("lookup"))
    )
    monkeypatch.setattr(discovery, "GalaxyCatalogue", unused)
    assert getattr(discovery, runner)([]) == 1
    assert "Usage" in capsys.readouterr().out


@pytest.mark.parametrize("flags", [["-v"], ["-vv"], ["--verbose"], ["-v", "-v"]])
def test_find_verbose_flags(flags, catalogue, monkeypatch):
    seen = {}

    def find(query, catalogue, source, verbose=False):
        seen.update(query=query, verbose=verbose)
        return services.FindResult(query=query, tool=None)

    monkeypatch.setattr(discovery.services, "find", find)
    monkeypatch.setattr(discovery, "GalaxyCatalogue", lambda: catalogue)
    monkeypatch.setattr(discovery.RsecSource, "load", lambda self: None)
    assert discovery.run_find(["samtools", *flags]) == 0
    assert seen == {"query": "samtools", "verbose": True}
