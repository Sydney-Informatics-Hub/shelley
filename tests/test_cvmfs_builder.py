#!/usr/bin/env python3
"""pytest coverage for CVMFSModuleBuilder: version resolution and shpc-based installation."""

import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shelley.builder.cvmfs_builder import CVMFSModuleBuilder, get_registry_tags
from shelley.commands.build import build_module

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

FAKE_VERSIONS = [
    ("samtools", "1.23.1--ha83d96e_0"),  # latest
    ("samtools", "1.21--h96c455f_1"),
    ("samtools", "1.21--h50ea8bc_0"),
]


@pytest.fixture
def builder(tmp_path) -> CVMFSModuleBuilder:
    return CVMFSModuleBuilder(lmod_modules=str(tmp_path / "modulefiles"))


def _make_subprocess_run(
    shpc_base: Path, install_rc: int = 0, install_out: str = "Module was created.\n"
):
    """Return a subprocess.run side-effect that handles shpc install and config calls."""

    def fake_run(cmd, **_):
        m = MagicMock()
        m.stderr = ""
        if "module_base" in cmd:
            m.returncode = 0
            m.stdout = str(shpc_base)
        else:
            m.returncode = install_rc
            m.stdout = install_out
        return m

    return fake_run


# ---------------------------------------------------------------------------
# Environment pre-flight
# ---------------------------------------------------------------------------


@pytest.mark.cvmfs
def test_shpc_is_executable():
    """Fallback path /opt/shpc/bin/shpc is present and executable even without module load."""
    result = subprocess.run(
        ["/opt/shpc/bin/shpc", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"shpc --version failed: {result.stderr}"


@pytest.mark.cvmfs
def test_shpc_on_path():
    """shpc must be on PATH for all build operations. Fix: module load shpc"""
    assert shutil.which("shpc") is not None, (
        "shpc not found on PATH, run 'module load shpc' before using shelley build "
        "or running the CVMFS integration tests."
    )


# ---------------------------------------------------------------------------
# Existing version-resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.cvmfs
@pytest.mark.parametrize(
    "tool_name,tool_version", [("samtools", "1.21"), ("plink2", "2.00a5.12")]
)
def test_search_tool_version_multiplebuilds(builder, tool_name, tool_version):
    # Both of these versions have multiple builds; interactive selection should be triggered.
    # Mock questionary so the test runs headlessly.
    with patch("shelley.builder.cvmfs_builder.questionary") as mock_q:
        available = builder._get_available_tools(tool_name)
        matches = [
            (t, v)
            for t, v in available
            if v == tool_version or v.split("--", 1)[0] == tool_version
        ]
        assert len(matches) > 1, "Precondition: test requires multiple builds"
        first_match = matches[0]
        mock_q.select.return_value.ask.return_value = first_match

        result = builder.search_tool_version(tool_name, tool_version)

        mock_q.select.assert_called_once()
        assert result[0] == tool_name
        assert result[1].split("--", 1)[0] == tool_version


@pytest.mark.cvmfs
@pytest.mark.parametrize(
    "tool_name,tool_version",
    [("samtools", "1.21--h96c455f_1"), ("plink2", "2.00a5.12--h4ac6f70_0")],
)
def test_search_tool_version_singlebuild(builder, tool_name, tool_version):
    # Both of these versions have only a single build
    exp = (tool_name, tool_version)
    get = builder.search_tool_version(tool_name, tool_version)
    assert get == exp


@pytest.mark.cvmfs
@pytest.mark.parametrize(
    "tool_name,tool_version,latest_version",
    [("samtools", None, "1.24--h9dcdb79_0"), ("plink2", None, "2.00a5.12--h4ac6f70_0")],
)
def test_search_tool_version_none(builder, tool_name, tool_version, latest_version):
    # When no version is provided, build the latest version
    exp = (tool_name, latest_version)
    get = builder.search_tool_version(tool_name, tool_version)
    assert get == exp


@pytest.mark.cvmfs
@pytest.mark.parametrize(
    "tool_name,tool_version", [("samtools", "1.23.1"), ("plink2", "2.00a5.12")]
)
def test_run_shpc_install_missing_cvmfs_path(builder, tool_name, tool_version):
    exitcode, _ = builder._run_shpc_install(tool_name, tool_version)
    assert exitcode == 1


@pytest.mark.cvmfs
@pytest.mark.parametrize(
    "tool_build", ["plink:1.90b7.7--h18e278d_1", "samtools:1.23.1--ha83d96e_0"]
)
def test_run_shpc_install_cvmfs_works(builder, tool_build):
    arg1 = f"quay.io/biocontainers/{tool_build}"
    arg2 = f"/cvmfs/singularity.galaxyproject.org/all/{tool_build}"
    exitcode, _ = builder._run_shpc_install(arg1, arg2)
    assert not exitcode, "shpc install should work, possibly a registry path issue"


# ---------------------------------------------------------------------------
# shpc_install unit tests
# ---------------------------------------------------------------------------


def test_shpc_install_success(builder, tmp_path):
    """Happy path: shpc install succeeds and symlink is created at the right path."""
    tool, version = "samtools", "1.21--h96c455f_1"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_make_subprocess_run(shpc_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value={
                "tags": {version: "sha256:x"},
                "aliases": {tool: f"/usr/local/bin/{tool}"},
            },
        ),
        patch.object(builder, "_ensure_local_registry_entry") as mock_ensure,
    ):
        dest = builder.shpc_install(tool, version)

    mock_ensure.assert_not_called()
    assert dest == builder.lmod_modules_path / tool / f"{version}.lua"
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()


def test_shpc_install_retries_after_uninstall(builder, tmp_path):
    """If shpc install fails (e.g. path-exists conflict), uninstall and retry once."""
    tool, version = "samtools", "1.21--h96c455f_1"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    install_calls = {"n": 0}
    uninstall_calls = {"n": 0}

    def fake_run(cmd, **_):
        m = MagicMock()
        m.stderr = ""
        if "module_base" in cmd:
            m.returncode = 0
            m.stdout = str(shpc_base)
        elif "config" in cmd:
            m.returncode = 0
            m.stdout = ""
        elif "uninstall" in cmd:
            uninstall_calls["n"] += 1
            m.returncode = 0
            m.stdout = ""
        else:
            install_calls["n"] += 1
            if install_calls["n"] == 1:
                m.returncode = 1
                m.stdout = "Error creating path, exiting."
            else:
                m.returncode = 0
                m.stdout = "Module was created.\n"
        return m

    with (
        patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=fake_run),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value={
                "tags": {version: "sha256:x"},
                "aliases": {tool: f"/usr/local/bin/{tool}"},
            },
        ),
    ):
        dest = builder.shpc_install(tool, version)

    assert install_calls["n"] == 2
    assert uninstall_calls["n"] == 1
    assert dest.is_symlink()


def test_shpc_install_hard_failure_raises(builder, tmp_path):
    """Persistent shpc failure (both attempts) raises RuntimeError containing the output."""
    shpc_base = tmp_path / "shpc_modules"
    version = "1.21--h96c455f_1"

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_make_subprocess_run(
                shpc_base, install_rc=1, install_out="Unexpected shpc error"
            ),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value={
                "tags": {version: "sha256:x"},
                "aliases": {"samtools": "/usr/local/bin/samtools"},
            },
        ),
    ):
        with pytest.raises(RuntimeError, match="shpc install failed"):
            builder.shpc_install("samtools", version)


def test_shpc_install_warns_when_no_aliases(builder, tmp_path):
    """Empty aliases + no -i/--interactive → a warning panel suggests rebuilding."""
    tool, version = "bandage", "0.8.1--hc9558a2_0"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_make_subprocess_run(shpc_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value={"tags": {version: "sha256:x"}, "aliases": {}},
        ),
        patch(
            "shelley.builder.cvmfs_builder.ShelleyStyle.create_warning_panel"
        ) as mock_warn,
    ):
        builder.shpc_install(tool, version)

    titles = [c.args[0] for c in mock_warn.call_args_list if c.args]
    assert "No aliases" in titles


def test_shpc_install_no_warning_when_aliases_present(builder, tmp_path):
    """Non-empty aliases → no 'No aliases' warning."""
    tool, version = "samtools", "1.21--h96c455f_1"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_make_subprocess_run(shpc_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value={
                "tags": {version: "sha256:x"},
                "aliases": {tool: f"/usr/local/bin/{tool}"},
            },
        ),
        patch(
            "shelley.builder.cvmfs_builder.ShelleyStyle.create_warning_panel"
        ) as mock_warn,
    ):
        builder.shpc_install(tool, version)

    titles = [c.args[0] for c in mock_warn.call_args_list if c.args]
    assert "No aliases" not in titles


# ---------------------------------------------------------------------------
# build_module input format tests
# ---------------------------------------------------------------------------
# These test that build_module correctly parses the tool spec and routes to
# shpc_install with the right arguments.  CVMFSModuleBuilder is patched at the
# class level so spec-parsing inside build_module is still exercised.


@pytest.fixture
def mock_builder_cls(tmp_path):
    """Patch CVMFSModuleBuilder inside cli with a mock instance."""
    fake_builder = MagicMock(spec=CVMFSModuleBuilder)
    fake_builder.search_tool_version.side_effect = lambda tool, ver=None: (
        tool,
        {
            None: "1.23.1--ha83d96e_0",
            "1.21": "1.21--h96c455f_1",
            "1.21--h96c455f_1": "1.21--h96c455f_1",
        }[ver],
    )
    fake_builder.shpc_install.return_value = tmp_path / "samtools" / "dummy.lua"
    fake_builder.list_versions.return_value = [v for _, v in FAKE_VERSIONS]

    with (
        patch("shelley.commands.build.CVMFSModuleBuilder", return_value=fake_builder),
        patch("pathlib.Path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("shelley.commands.build.ShelleyStyle.create_status") as mock_status,
        patch("shelley.commands.build.console"),
    ):
        mock_status.return_value.__enter__ = MagicMock(return_value=None)
        mock_status.return_value.__exit__ = MagicMock(return_value=False)
        yield fake_builder


def test_build_no_version(mock_builder_cls):
    """build_module('samtools') installs the latest tag."""
    result = build_module("samtools")

    assert result is True
    mock_builder_cls.shpc_install.assert_called_once_with(
        "samtools", "1.23.1--ha83d96e_0", interactive=False, status=None
    )


def test_build_short_version(mock_builder_cls):
    """build_module('samtools/1.21') installs the full tag after version resolution."""
    result = build_module("samtools/1.21")

    assert result is True
    mock_builder_cls.shpc_install.assert_called_once_with(
        "samtools", "1.21--h96c455f_1", interactive=False, status=None
    )


def test_build_full_tag(mock_builder_cls):
    """build_module('samtools/1.21--h96c455f_1') installs the exact tag without prompting."""
    result = build_module("samtools/1.21--h96c455f_1")

    assert result is True
    mock_builder_cls.shpc_install.assert_called_once_with(
        "samtools", "1.21--h96c455f_1", interactive=False, status=None
    )


# ---------------------------------------------------------------------------
# _ensure_local_registry_entry alias generation
# ---------------------------------------------------------------------------


def test_ensure_local_registry_populates_aliases_on_miss(builder, tmp_path):
    """When upstream registry returns 404, aliases are populated via guts diff."""
    fake_aliases = [{"name": "bwa", "command": "bwa"}]
    with (
        patch("shelley.builder.cvmfs_builder.subprocess.run") as mock_run,
        patch(
            "shelley.builder.cvmfs_builder.extract_aliases", return_value=fake_aliases
        ),
        patch.object(builder, "_compute_sha256", return_value="abc123"),
    ):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        builder._ensure_local_registry_entry(
            "bwa",
            "0.7.17--hed695b0_7",
            "/cvmfs/.../bwa:0.7.17--hed695b0_7",
            "quay.io/biocontainers/bwa",
            local_registry=str(tmp_path),
        )
    import yaml

    config = yaml.safe_load(
        (tmp_path / "quay.io/biocontainers/bwa/container.yaml").read_text()
    )
    assert config["aliases"] == fake_aliases


def test_ensure_local_registry_always_regenerates_aliases(builder, tmp_path):
    """Aliases from a previous version are replaced by guts diff for the current container.

    Stale aliases (e.g. salmon from star-fusion 1.10.1) must not carry over to an older
    install that doesn't have those binaries.
    """
    fake_aliases = [{"name": "samtools", "command": "samtools"}]
    stale_aliases = [
        {"name": "salmon", "command": "salmon"},
        {"name": "samtools", "command": "samtools"},
    ]
    registry_dir = tmp_path / "quay.io/biocontainers/samtools"
    registry_dir.mkdir(parents=True)
    # Pre-existing entry with non-empty aliases from a different version
    (registry_dir / "container.yaml").write_text(
        f"docker: quay.io/biocontainers/samtools\naliases: {stale_aliases}\ntags: {{}}\n"
    )
    with (
        patch("shelley.builder.cvmfs_builder.subprocess.run") as mock_run,
        patch(
            "shelley.builder.cvmfs_builder.extract_aliases", return_value=fake_aliases
        ),
        patch.object(builder, "_compute_sha256", return_value="abc123"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        builder._ensure_local_registry_entry(
            "samtools",
            "1.21--h96c455f_1",
            "/cvmfs/.../samtools:1.21--h96c455f_1",
            "quay.io/biocontainers/samtools",
            local_registry=str(tmp_path),
        )
    import yaml

    config = yaml.safe_load((registry_dir / "container.yaml").read_text())
    assert config["aliases"] == fake_aliases


def test_extract_aliases_returns_empty_on_failure():
    """extract_aliases degrades gracefully when the sparse clone or diff fails."""
    from shelley.builder.guts_integration import extract_aliases

    with patch(
        "shelley.builder.guts_integration._sparse_clone_base_manifests",
        side_effect=subprocess.CalledProcessError(1, "git"),
    ):
        result = extract_aliases("/cvmfs/foo/bar:1.0")
    assert result == []


@contextmanager
def _scripted_guts_diff(diff_data):
    """Patch guts so extract_aliases sees ``diff_data`` as the diff result.

    Stubs the clone and the supplementary-db merge too, so nothing touches the
    network or the filesystem.
    """
    gen = MagicMock()
    gen.diff.return_value = {"docker.io/x:1.0": {"diff": diff_data}}
    with (
        patch(
            "shelley.builder.guts_integration._sparse_clone_base_manifests",
            return_value="/tmp/does-not-matter",
        ),
        patch("shelley.builder.guts_integration._merge_supplementary_db"),
        patch("shelley.builder.guts_integration.shutil.rmtree"),
        patch("shelley.builder.guts_integration.ManifestGenerator", return_value=gen),
    ):
        yield


def test_extract_aliases_ignores_paths_outside_bin_dirs():
    """Only executables in a bin/sbin directory become aliases."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff(
        {"unique_paths": ["/usr/local/bin/samtools", "/opt/data/reference.fa"]}
    ):
        assert extract_aliases("/cvmfs/x") == [
            {"name": "samtools", "command": "samtools"}
        ]


def test_extract_aliases_dedupes_the_same_executable_in_two_path_dirs():
    """A binary present in two PATH dirs yields one alias, not two identical ones."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff({"unique_paths": ["/usr/bin/bwa", "/usr/local/bin/bwa"]}):
        assert extract_aliases("/cvmfs/x") == [{"name": "bwa", "command": "bwa"}]


def test_extract_aliases_drops_shadowed_paths_by_default():
    """Base binaries guts shadowed must not come back as aliases."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff(
        {
            "unique_paths": ["/usr/local/bin/samtools"],
            "shadowed_paths": ["/sbin/devmem", "/usr/bin/tput"],
        }
    ):
        assert extract_aliases("/cvmfs/x") == [
            {"name": "samtools", "command": "samtools"}
        ]


def test_extract_aliases_keep_readmits_a_tool_named_like_a_base_binary():
    """A tool really called `sort` is shadowed by coreutils; keep= rescues it."""
    from shelley.builder.guts_integration import extract_aliases

    diff = {
        "unique_paths": [],
        "shadowed_paths": ["/usr/local/bin/sort", "/sbin/devmem"],
    }
    with _scripted_guts_diff(diff):
        assert extract_aliases("/cvmfs/x", keep="sort") == [
            {"name": "sort", "command": "sort"}
        ]


def test_extract_aliases_tolerates_a_diff_without_shadowed_paths():
    """Guards against an older container-guts that predates the new key."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff({"unique_paths": ["/usr/local/bin/fastp"]}):
        assert extract_aliases("/cvmfs/x", keep="fastp") == [
            {"name": "fastp", "command": "fastp"}
        ]


def test_shpc_install_skips_local_entry_for_upstream_tool(builder, tmp_path):
    """When version is in upstream registry, _ensure_local_registry_entry is not called."""
    tool, version = "samtools", "1.21--h96c455f_1"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_make_subprocess_run(shpc_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value={
                "tags": {version: "sha256:x"},
                "aliases": {tool: f"/usr/local/bin/{tool}"},
            },
        ),
        patch.object(builder, "_ensure_local_registry_entry") as mock_ensure,
    ):
        dest = builder.shpc_install(tool, version)

    mock_ensure.assert_not_called()
    assert dest == builder.lmod_modules_path / tool / f"{version}.lua"
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()


def test_shpc_install_upstream_with_edit_reroutes_to_local(builder, tmp_path):
    """Editing an UPSTREAM tool must still create a local entry (the reroute).

    Regression guard: `--interactive` on a remote-registry version has to build
    through a local shpc registry entry so the edits persist and shadow upstream.
    """
    tool, version = "bcftools", "1.16--haef29d1_2"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    with (
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            side_effect=_make_subprocess_run(shpc_base),
        ),
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config",
            return_value={
                "tags": {version: "sha256:x"},
                "aliases": {tool: f"/usr/local/bin/{tool}"},
            },
        ),
        patch.object(builder, "_register_local_registry") as mock_register,
        patch.object(
            builder,
            "_ensure_local_registry_entry",
            return_value=[{"name": tool, "command": tool}],
        ) as mock_ensure,
    ):
        builder.shpc_install(tool, version, interactive=True)

    # in_upstream is True, but interactive forces the local-registry route.
    mock_ensure.assert_called_once()
    assert mock_ensure.call_args.kwargs.get("in_upstream") is True
    assert mock_ensure.call_args.kwargs.get("interactive") is True
    mock_register.assert_called_once()


def test_shpc_install_not_in_registry_calls_extract_aliases(builder, tmp_path):
    """Full chain: version absent from upstream → _ensure_local_registry_entry runs
    → extract_aliases called → YAML written with aliases → single shpc install → symlink."""
    tool, version = "bwa", "0.7.17--hed695b0_7"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    local_registry = tmp_path / "registry"
    install_calls = {"n": 0}

    def fake_run(cmd, **_):
        m = MagicMock()
        m.stderr = ""
        if "module_base" in cmd:
            m.returncode = 0
            m.stdout = str(shpc_base)
        elif "curl" in cmd:
            m.returncode = 1
            m.stdout = ""
        elif "config" in cmd or "uninstall" in cmd:
            m.returncode = 0
            m.stdout = ""
        else:
            install_calls["n"] += 1
            m.returncode = 0
            m.stdout = "Module was created.\n"
        return m

    fake_aliases = [{"name": "bwa", "command": "bwa"}]

    # Wrap _ensure_local_registry_entry to redirect writes to tmp_path
    real_ensure = builder._ensure_local_registry_entry

    def wrapped_ensure(tool_name, ver, container_path, uri, **kwargs):
        kwargs.pop("local_registry", None)
        return real_ensure(
            tool_name,
            ver,
            container_path,
            uri,
            local_registry=str(local_registry),
            **kwargs,
        )

    expected_cvmfs = str(builder.cvmfs_singularity_path / f"{tool}:{version}")

    with (
        patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=fake_run),
        patch("shelley.builder.cvmfs_builder._load_registry_config", return_value={}),
        patch.object(
            builder, "_ensure_local_registry_entry", side_effect=wrapped_ensure
        ),
        patch(
            "shelley.builder.cvmfs_builder.extract_aliases", return_value=fake_aliases
        ) as mock_extract,
        patch.object(builder, "_compute_sha256", return_value="deadbeef"),
    ):
        dest = builder.shpc_install(tool, version)

    # keep=tool so a tool named like a base binary survives guts' basename filter
    mock_extract.assert_called_once_with(expected_cvmfs, keep=tool)

    import yaml

    config = yaml.safe_load(
        (
            local_registry / "quay.io" / "biocontainers" / tool / "container.yaml"
        ).read_text()
    )
    assert config["aliases"] == fake_aliases
    assert install_calls["n"] == 1
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()


def test_shpc_install_creates_local_entry_when_not_in_upstream(builder, tmp_path):
    """Version absent from upstream: _shpc_uninstall, then _ensure_local_registry_entry,
    then a single shpc install (no retry)."""
    tool, version = "fastp", "0.20.0--hdbcaa40_0"
    shpc_base = tmp_path / "shpc_modules"
    src = shpc_base / "quay.io" / "biocontainers" / tool / version / "module.lua"
    src.parent.mkdir(parents=True)
    src.touch()

    call_order = []

    def fake_run(cmd, **_):
        m = MagicMock()
        m.stderr = ""
        if "module_base" in cmd:
            m.returncode = 0
            m.stdout = str(shpc_base)
        elif "uninstall" in cmd:
            call_order.append("uninstall")
            m.returncode = 0
            m.stdout = ""
        elif "config" in cmd:
            m.returncode = 0
            m.stdout = ""
        else:
            call_order.append("install")
            m.returncode = 0
            m.stdout = "Module was created.\n"
        return m

    def fake_ensure(*args, **kwargs):
        call_order.append("ensure")

    with (
        patch("shelley.builder.cvmfs_builder.subprocess.run", side_effect=fake_run),
        patch("shelley.builder.cvmfs_builder._load_registry_config", return_value={}),
        patch.object(builder, "_ensure_local_registry_entry", side_effect=fake_ensure),
        patch.object(builder, "_register_local_registry"),
    ):
        dest = builder.shpc_install(tool, version)

    assert call_order == ["uninstall", "ensure", "install"]
    assert dest.is_symlink()


def _read_aliases(local_registry, tool):
    import yaml

    return yaml.safe_load(
        (
            local_registry / "quay.io" / "biocontainers" / tool / "container.yaml"
        ).read_text()
    )["aliases"]


def test_ensure_local_registry_entry_interactive_narrows(builder, tmp_path):
    """interactive=True → edit_aliases_interactive result is what gets written."""
    tool, version = "vcftools", "0.1.16--pl5321hdcf5f25_9"
    local_registry = tmp_path / "registry"
    container_path = str(builder.cvmfs_singularity_path / f"{tool}:{version}")

    detected = [
        {"name": "vcftools", "command": "vcftools"},
        {"name": "devmem", "command": "devmem"},
        {"name": "telnet", "command": "telnet"},
    ]
    edited = [detected[0]]

    with (
        patch("shelley.builder.cvmfs_builder.extract_aliases", return_value=detected),
        patch(
            "shelley.builder.cvmfs_builder.edit_aliases_interactive",
            return_value=edited,
        ) as mock_edit,
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            return_value=MagicMock(returncode=1, stdout="", stderr=""),
        ),
        patch.object(builder, "_compute_sha256", return_value="deadbeef"),
    ):
        written = builder._ensure_local_registry_entry(
            tool,
            version,
            container_path,
            f"quay.io/biocontainers/{tool}",
            local_registry=str(local_registry),
            interactive=True,
        )

    mock_edit.assert_called_once_with(detected)
    assert written == edited
    assert _read_aliases(local_registry, tool) == edited


def test_ensure_local_registry_entry_no_edit_keeps_all(builder, tmp_path):
    """interactive=False (default) → no prompt; all detected aliases are written."""
    tool, version = "vcftools", "0.1.16--pl5321hdcf5f25_9"
    local_registry = tmp_path / "registry"
    container_path = str(builder.cvmfs_singularity_path / f"{tool}:{version}")

    detected = [
        {"name": "vcftools", "command": "vcftools"},
        {"name": "telnet", "command": "telnet"},
    ]

    with (
        patch("shelley.builder.cvmfs_builder.extract_aliases", return_value=detected),
        patch("shelley.builder.cvmfs_builder.edit_aliases_interactive") as mock_edit,
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            return_value=MagicMock(returncode=1, stdout="", stderr=""),
        ),
        patch.object(builder, "_compute_sha256", return_value="deadbeef"),
    ):
        builder._ensure_local_registry_entry(
            tool,
            version,
            container_path,
            f"quay.io/biocontainers/{tool}",
            local_registry=str(local_registry),
        )

    mock_edit.assert_not_called()
    assert _read_aliases(local_registry, tool) == detected


def test_ensure_local_registry_entry_upstream_edits_upstream_aliases(builder, tmp_path):
    """in_upstream=True → aliases seeded from the (downloaded) upstream config, not guts."""
    tool, version = "star", "2.7.11a--h0033a41_0"
    local_registry = tmp_path / "registry"
    container_path = str(builder.cvmfs_singularity_path / f"{tool}:{version}")

    upstream = {
        "docker": f"quay.io/biocontainers/{tool}",
        "tags": {},
        "aliases": {"STAR": "/usr/local/bin/STAR"},
    }
    # rename is name-only: command (the full upstream path) is preserved
    renamed = [{"name": "star", "command": "/usr/local/bin/STAR"}]

    def fake_edit(aliases):
        # editor receives the normalized upstream aliases (command path preserved)
        assert aliases == [{"name": "STAR", "command": "/usr/local/bin/STAR"}]
        return renamed

    with (
        patch("shelley.builder.cvmfs_builder.extract_aliases") as mock_extract,
        patch(
            "shelley.builder.cvmfs_builder._load_registry_config", return_value=upstream
        ),
        patch(
            "shelley.builder.cvmfs_builder.edit_aliases_interactive",
            side_effect=fake_edit,
        ),
        patch(
            "shelley.builder.cvmfs_builder.subprocess.run",
            return_value=MagicMock(returncode=1, stdout="", stderr=""),
        ),
        patch.object(builder, "_compute_sha256", return_value="deadbeef"),
    ):
        written = builder._ensure_local_registry_entry(
            tool,
            version,
            container_path,
            f"quay.io/biocontainers/{tool}",
            local_registry=str(local_registry),
            interactive=True,
            in_upstream=True,
        )

    mock_extract.assert_not_called()
    assert written == renamed
    assert _read_aliases(local_registry, tool) == renamed


# ---------------------------------------------------------------------------
# CVMFS regression: star-fusion 1.0.0 alias correctness
# ---------------------------------------------------------------------------


@pytest.mark.cvmfs
def test_extract_aliases_star_fusion_1_0_0():
    """star-fusion 1.0.0 must alias STAR but never salmon.

    Regression: salmon appeared because aliases were inherited from a newer
    build (which bundles salmon) rather than extracted from the 1.0.0 SIF.
    Requires Singularity on PATH (in addition to CVMFS).
    """
    if shutil.which("singularity") is None:
        pytest.skip("singularity not on PATH")
    from shelley.builder.guts_integration import extract_aliases

    sif = "/cvmfs/singularity.galaxyproject.org/all/star-fusion:1.0.0--pl5.22.0_0"
    aliases = extract_aliases(sif)
    alias_names = {a["name"] for a in aliases}
    assert "STAR" in alias_names, f"STAR should be aliased; got: {sorted(alias_names)}"
    assert "salmon" not in alias_names, (
        f"salmon must NOT be aliased; got: {sorted(alias_names)}"
    )


# ---------------------------------------------------------------------------
# CVMFS regression: newly_created flag
# ---------------------------------------------------------------------------

_CVMFS = "/cvmfs/singularity.galaxyproject.org/all"


@pytest.mark.cvmfs
@pytest.mark.parametrize(
    "tool,version",
    [
        ("fastp", "0.20.0--hdbcaa40_0"),
        ("sambamba", "0.8.1--hadffe2f_1"),
        ("samblaster", "0.1.24--hc9558a2_3"),
        ("samtools", "1.19--h50ea8bc_0"),
        ("blast", "2.5.0--hc0b0e79_3"),
        ("star-fusion", "1.0.0--pl5.22.0_0"),
    ],
)
def test_ensure_local_registry_entry_newly_created(builder, tmp_path, tool, version):
    """Tools absent from upstream registry: _ensure_local_registry_entry writes the YAML tag."""
    with (
        patch("shelley.builder.cvmfs_builder.extract_aliases", return_value=[]),
        patch.object(builder, "_compute_sha256", return_value="deadbeef"),
    ):
        builder._ensure_local_registry_entry(
            tool,
            version,
            f"{_CVMFS}/{tool}:{version}",
            f"quay.io/biocontainers/{tool}",
            local_registry=str(tmp_path),
        )
    import yaml

    config = yaml.safe_load(
        (tmp_path / f"quay.io/biocontainers/{tool}/container.yaml").read_text()
    )
    assert version in config.get("tags", {}), (
        f"{tool}:{version} tag missing from written YAML"
    )


@pytest.mark.cvmfs
@pytest.mark.parametrize(
    "tool,version",
    [
        ("fastqc", "0.12.1--hdfd78af_0"),
        ("multiqc", "1.19--pyhdfd78af_0"),
        ("salmon", "1.10.1--h7e5ed60_0"),
        ("bcftools", "1.23.1--hb2cee57_0"),
        ("bwa-mem2", "2.2.1--he70b90d_8"),
        ("star", "2.7.11a--h0033a41_0"),
    ],
)
def test_get_registry_tags_upstream_only_finds_known_versions(tool, version):
    """get_registry_tags(upstream_only=True) finds versions present in upstream shpc-registry."""
    tags = get_registry_tags(tool, upstream_only=True)
    assert version in tags, (
        f"{tool}:{version} not in upstream tags; got: {sorted(tags)[:5]}"
    )


# ---------------------------------------------------------------------------
# Unit tests: tools absent from CVMFS raise ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ["parabricks", "seurat"])
def test_search_tool_version_not_in_cvmfs(builder, tool_name):
    """Tools absent from CVMFS raise ValueError with an informative message."""
    with patch.object(builder, "_get_available_tools", return_value=[]):
        with pytest.raises(ValueError, match="not found"):
            builder.search_tool_version(tool_name)
