"""The opt-in build path end to end: resolve as the user, then elevate once"""

import sys
from unittest.mock import MagicMock

import pytest

import shelley.client.new_build as new_build
from shelley import privilege, services
from shelley.errors import AmbiguousTag, TagNotFound
from shelley.galaxy.catalogue import GalaxyCatalogue
from shelley.galaxy.exposer import ShpcExposer
from shelley.tools.lmod import Lmod

from .conftest import golden_entries
from .fakes import UPSTREAM_SAMTOOLS, FakeRegistry, FakeShpc


@pytest.fixture
def catalogue(galaxy_mount, galaxy_snapshot, monkeypatch):
    entries = golden_entries()
    cat = GalaxyCatalogue(
        snapshot=galaxy_snapshot(entries), mount=galaxy_mount(entries)
    )
    monkeypatch.setattr(new_build, "GalaxyCatalogue", lambda: cat)
    return cat


@pytest.fixture
def sudo(monkeypatch):
    """Pretend /apps needs root; record re-execs instead of running sudo."""
    calls = []
    monkeypatch.setattr(privilege, "needs_root", lambda: True)
    monkeypatch.setattr(privilege, "reexec", lambda args: calls.append(args) or 0)
    return calls


@pytest.fixture
def fake_build_env(monkeypatch):
    """Run the root half in-process against the tmp build roots, with fakes."""
    shpc = FakeShpc()
    monkeypatch.setattr(privilege, "needs_root", lambda: False)
    monkeypatch.setattr(Lmod, "load_build_modules", lambda self: True)
    monkeypatch.setattr(
        new_build,
        "ShpcExposer",
        lambda lmod: ShpcExposer(
            registry=FakeRegistry(
                {"quay.io/biocontainers/samtools": UPSTREAM_SAMTOOLS}
            ),
            shpc=shpc,
            lmod=lmod,
            discover=lambda sif, keep=None: [{"name": keep, "command": keep}],
        ),
    )
    return shpc


# ------------------------------------------------------------------ services
@pytest.mark.parametrize(
    ("spec", "parsed"),
    [
        ("samtools", ("samtools", None)),
        ("samtools/1.21", ("samtools", "1.21")),
        ("samtools:1.21--h50ea8bc_3", ("samtools", "1.21--h50ea8bc_3")),
        ("samtools/", ("samtools", None)),
    ],
)
def test_parse_spec(spec, parsed):
    assert services.parse_spec(spec) == parsed


def test_resolve_reports_the_default_and_the_versions(catalogue):
    item = services.resolve("samtools", catalogue)
    assert item.tag.raw == "1.21--h50ea8bc_3" and item.defaulted
    assert item.versions == ("1.21", "1.10", "1.9")
    assert item.sif.name == "samtools:1.21--h50ea8bc_3"


def test_resolve_asks_the_chooser_for_an_ambiguous_version(catalogue):
    seen = []

    def choose(err: AmbiguousTag) -> str:
        seen.append(err.matches)
        return err.matches[-1]

    item = services.resolve("seqtk/1.5", catalogue, choose)
    assert seen == [["1.5--h577a1d6_1", "1.5--h577a1d6_0"]]
    assert item.tag.raw == "1.5--h577a1d6_0"


def test_resolve_all_keeps_going_after_a_failure(catalogue):
    resolved, failed = services.resolve_all(
        ["samtools", "nosuchtool", "lofreq"], catalogue
    )
    assert [r.tool for r in resolved] == ["samtools", "lofreq"]
    assert [f.spec for f in failed] == ["nosuchtool"]
    assert isinstance(failed[0].error, TagNotFound)


@pytest.mark.parametrize(
    "value", ["../etc:1", "samtools:../../x", "samtools", ":1.0", "a b:1"]
)
def test_resolved_tag_values_are_validated_before_root_uses_them(catalogue, value):
    with pytest.raises(services.InvalidSpec):
        services.parse_resolved(value, catalogue)


def test_resolved_tag_must_exist_on_the_mount(catalogue):
    with pytest.raises(TagNotFound):
        services.parse_resolved("samtools:9.9--h0", catalogue)


# ------------------------------------------------------------------ CLI (user half)
def test_bad_spec_is_reported_before_any_sudo_prompt(catalogue, sudo):
    assert new_build.run(["nosuchtool"]) == 1
    assert sudo == []


def test_good_spec_reexecs_once_with_the_resolved_tag(catalogue, sudo):
    assert new_build.run(["samtools"]) == 0
    assert sudo == [["build", "--resolved-tag", "samtools:1.21--h50ea8bc_3"]]


def test_interactive_flag_is_passed_to_the_root_child(catalogue, sudo):
    new_build.run(["samtools/1.10", "-i"])
    assert sudo == [
        ["build", "--resolved-tag", "samtools:1.10--h2e538c0_3", "--interactive"]
    ]


def test_ambiguous_version_is_chosen_before_sudo(catalogue, sudo, monkeypatch):
    monkeypatch.setattr(new_build, "_chooser", lambda cat: lambda err: err.matches[0])
    new_build.run(["seqtk/1.5"])
    assert sudo == [["build", "--resolved-tag", "seqtk:1.5--h577a1d6_1"]]


def test_batch_resolves_everything_then_elevates_once(catalogue, sudo, tmp_path):
    tools = tmp_path / "tools.txt"
    tools.write_text("samtools  # comment\n\nnosuchtool\nlofreq/2.1.5\n")
    assert new_build.run([str(tools)]) == 1  # one spec failed
    assert sudo == [
        [
            "build",
            "--resolved-tag",
            "samtools:1.21--h50ea8bc_3",
            "--resolved-tag",
            "lofreq:2.1.5--py_0",
        ]
    ]


# ------------------------------------------------------------------ CLI (root half)
def test_root_child_builds_the_resolved_tag(catalogue, fake_build_env):
    code = new_build.run(["--resolved-tag", "samtools:1.21--h50ea8bc_3"])
    assert code == 0
    assert fake_build_env.calls[0][:2] == (
        "install",
        "quay.io/biocontainers/samtools:1.21--h50ea8bc_3",
    )


def test_root_child_rejects_an_unsafe_value(catalogue, fake_build_env):
    assert new_build.run(["--resolved-tag", "../../etc:passwd"]) == 1
    assert fake_build_env.calls == []


def test_in_process_build_when_apps_is_writable(catalogue, fake_build_env):
    assert new_build.run(["samtools/1.10"]) == 0
    assert (
        fake_build_env.calls[0][1] == "quay.io/biocontainers/samtools:1.10--h2e538c0_3"
    )


# ------------------------------------------------------------------ routing
@pytest.mark.parametrize("opt_in", [None, "1"])
def test_cli_routes_build_to_the_new_path_by_default(monkeypatch, opt_in):
    """Default since 3a; a leftover ``SHELLEY_NEW_BUILD=1`` changes nothing."""
    from shelley.client import cli

    seen = []
    monkeypatch.delenv("SHELLEY_LEGACY_BUILD", raising=False)
    if opt_in:
        monkeypatch.setenv("SHELLEY_NEW_BUILD", opt_in)
    monkeypatch.setattr(new_build, "run", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(
        cli, "build_module", lambda *a, **k: pytest.fail("old path used")
    )
    monkeypatch.setattr(sys, "argv", ["shelley", "build", "samtools", "-i"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0 and seen == [["samtools", "-i"]]


def test_cli_keeps_the_old_path_behind_the_escape_hatch(monkeypatch):
    from shelley.client import cli

    seen = []
    monkeypatch.setenv("SHELLEY_LEGACY_BUILD", "1")
    monkeypatch.setattr(new_build, "run", lambda argv: pytest.fail("new path used"))
    monkeypatch.setattr(
        cli, "build_module", lambda spec, interactive=False: seen.append(spec) or True
    )
    monkeypatch.setattr(sys, "argv", ["shelley", "build", "samtools"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0 and seen == ["samtools"]


def test_repl_routes_build_to_the_new_path_by_default(monkeypatch):
    from shelley.commands import interactive

    seen = []
    monkeypatch.delenv("SHELLEY_LEGACY_BUILD", raising=False)
    monkeypatch.setattr(new_build, "run", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(
        interactive, "build_module", lambda *a, **k: pytest.fail("old path used")
    )
    monkeypatch.setattr(interactive, "print_banner", lambda *a, **k: None)
    monkeypatch.setattr(interactive, "print_rule", lambda *a, **k: None)
    console = MagicMock()
    console.input.side_effect = ["build samtools -i", "exit"]
    monkeypatch.setattr(interactive, "console", console)
    interactive.interactive_mode()
    assert seen == [["samtools", "-i"]]


def test_root_child_inherits_the_escape_hatch(monkeypatch):
    monkeypatch.setenv("SHELLEY_LEGACY_BUILD", "1")
    assert "SHELLEY_LEGACY_BUILD=1" in privilege.sudo_env_args()


def test_ambiguous_version_without_a_terminal_is_a_clean_cancel(
    catalogue, sudo, monkeypatch
):
    class NoTerminal:
        def ask(self):
            raise EOFError

    monkeypatch.setattr(new_build.questionary, "select", lambda *a, **k: NoTerminal())
    assert new_build.run(["seqtk/1.5"]) == 1
    assert sudo == []
