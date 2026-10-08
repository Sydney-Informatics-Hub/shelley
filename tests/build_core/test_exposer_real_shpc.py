"""Test the exposer class against the real shpc, Singularity and Galaxy mounts.

Builds ``seqtk:r93--0`` (3.5 MB, in the upstream registry) into the tmp build roots,
checks it loads and runs through Lmod, then injects a failure into a rebuild and checks
the tree is unchanged and the module still works. Skips itself without the mount, shpc,
Lmod or network.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from shelley.galaxy.catalogue import GalaxyCatalogue
from shelley.galaxy.exposer import ShpcExposer
from shelley.tags import Tag
from shelley.tools import net
from shelley.tools.lmod import Lmod
from shelley.tools.shpc import ShpcFailed
from shelley.utils import globals as gl

from .tree import changes, snapshot

MOUNT = Path("/cvmfs/singularity.galaxyproject.org/all")
LMOD_INIT = Path("/usr/share/lmod/lmod/init/bash")
pytestmark = [pytest.mark.cvmfs, pytest.mark.shpc, pytest.mark.network]


@pytest.fixture
def real_env():
    if not (shutil.which("shpc") or Path("/opt/shpc/bin/shpc").exists()):
        pytest.skip("shpc not installed")
    if not LMOD_INIT.exists():
        pytest.skip("Lmod not installed")
    if not net.diagnose(
        "https://raw.githubusercontent.com/singularityhub/shpc-registry/main/README.md"
    ).ok:
        pytest.skip("GitHub not reachable")
    Lmod().load_build_modules()


def _runs(tag: Tag) -> bool:
    script = (
        f"source {LMOD_INIT} && module use {gl.lmod_modules()} && module load singularity "
        f"&& module load seqtk/{tag.raw} && seqtk 2>&1 | head -2"
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return "Usage" in out.stdout + out.stderr


def test_real_build_and_failed_rebuild(real_env, monkeypatch):
    cat = GalaxyCatalogue(mount=MOUNT)
    tag = cat.resolve("seqtk", "r93--0")
    sif = cat.verify("seqtk", tag)
    exp = ShpcExposer()

    exp.apply(exp.plan("seqtk", tag, sif))
    assert _runs(tag)

    plan = exp.plan("seqtk", tag, sif)
    assert plan.replace_existing
    roots = [gl.shpc_base(), gl.local_registry(), gl.lmod_modules()]
    before = snapshot(*roots)

    def fail_link(self, *args, **kwargs):
        raise ShpcFailed("link", "seqtk", "injected")

    monkeypatch.setattr(Lmod, "link", fail_link)
    with pytest.raises(ShpcFailed):
        exp.apply(plan)
    assert changes(before, snapshot(*roots)) == []
    assert _runs(tag)
