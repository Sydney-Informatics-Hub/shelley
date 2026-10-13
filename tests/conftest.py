import os
from pathlib import Path

import pytest

CVMFS_PATH = Path("/cvmfs/singularity.galaxyproject.org/all")


def pytest_configure(config):
    config.addinivalue_line("markers", "cvmfs: requires a live CVMFS mount")
    config.addinivalue_line(
        "markers",
        "network: requires outbound network access (curl to GitHub shpc-registry)",
    )
    config.addinivalue_line(
        "markers", "shpc: requires the shpc package to be importable"
    )
    config.addinivalue_line(
        "markers",
        "no_shared_root_redirect: exercise the real /apps build roots, not a tmp dir",
    )


@pytest.fixture(autouse=True)
def _skip_without_cvmfs(request):
    if request.node.get_closest_marker("cvmfs") and not CVMFS_PATH.exists():
        pytest.skip("CVMFS not mounted")


@pytest.fixture(autouse=True)
def _shared_roots_in_tmp(request, tmp_path_factory, monkeypatch):
    """Redirect the shared build roots into a tmp dir for every test.

    `shelley build` writes to /apps/shpc, /apps/local and /apps/Modules/modulefiles and
    chmods what it creates there. Without this redirect the unit suite would need write
    access to /apps, and the live @pytest.mark.cvmfs install tests would install into the
    developer's own home directory (which is what they do today).

    Tests that need to exercise the real default paths opt out with
    @pytest.mark.no_shared_root_redirect.
    """
    if request.node.get_closest_marker("no_shared_root_redirect"):
        yield None
        return

    base = tmp_path_factory.mktemp("shelley-shared")
    monkeypatch.setenv("SHELLEY_SHPC_BASE", str(base / "shpc"))
    monkeypatch.setenv("SHELLEY_LOCAL_REGISTRY", str(base / "local"))
    monkeypatch.setenv("SHELLEY_LMOD_MODULES_PATH", str(base / "modulefiles"))

    # Import here: shelley.utils.globals resolves these env vars per call, but the
    # helpers must not run at collection time.
    from shelley.builder.shpc_settings import ensure_shared_shpc_settings
    from shelley.utils.perms import ensure_shared_layout

    previous_umask = os.umask(0o022)
    try:
        ensure_shared_layout()
        ensure_shared_shpc_settings()
        yield base
    finally:
        os.umask(previous_umask)
