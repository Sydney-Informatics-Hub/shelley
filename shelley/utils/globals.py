"""Paths and permission modes for the shared, multi-user build layout.

Every build artifact lives under a *shared* prefix so that any user on the machine
can `module load` a tool that any admin built. The constants below are the
documented defaults; the resolver functions beneath them read an environment
override on each call, which is what makes the layout redirectable in tests (see
tests/conftest.py) and adaptable on a differently-provisioned host.

Read paths through the resolvers, not the constants: a ``from ... import SHPC_BASE``
binds a copy at import time, so an override set afterwards would be ignored.
"""

import os
from pathlib import Path

CVMFS_GALAXY_SINGULARITY_PATH = "/cvmfs/singularity.galaxyproject.org/all"
LMOD_MODULES_PATH = "/apps/Modules/modulefiles"
LOCAL_REGISTRY = "/apps/local"
SHPC_BASE = "/apps/shpc"

# The upstream shpc registry. Named explicitly because shelley's settings file
# replaces shpc's `registry` list wholesale rather than appending to it.
UPSTREAM_SHPC_REGISTRY = "https://github.com/singularityhub/shpc-registry"

# Environment (Lmod) modules loaded before a build so shpc and singularity are on
# PATH. Loaded only on the build path (see shelley.utils.modules.load_build_modules).
BUILD_MODULES = ("shpc", "singularity")

# Path to the bundled data directory (shelley/data/)
DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

# Permission model for shared artifacts: root-owned, world read + traverse +
# execute, never group- or other-writable. Only the privileged build path writes
# here, so read access for everyone is both sufficient and the safer choice.
SHARED_UMASK = 0o022
SHARED_DIR_MODE = 0o755
SHARED_FILE_MODE = 0o644
SHARED_EXEC_MODE = 0o755


def _resolve(env_var: str, default: str) -> Path:
    """Return the env override for a build root, falling back to the default."""
    return Path(os.environ.get(env_var) or default)


def shpc_base() -> Path:
    """Root of the shared shpc install tree (SHELLEY_SHPC_BASE)."""
    return _resolve("SHELLEY_SHPC_BASE", SHPC_BASE)


def local_registry() -> Path:
    """Local shpc registry holding shelley-authored container.yaml entries."""
    return _resolve("SHELLEY_LOCAL_REGISTRY", LOCAL_REGISTRY)


def lmod_modules() -> Path:
    """Lmod modulefiles directory that `module avail` scans."""
    return _resolve("SHELLEY_LMOD_MODULES_PATH", LMOD_MODULES_PATH)


def cvmfs_singularity() -> Path:
    """CVMFS directory of Galaxy-built SIF containers (read-only)."""
    return _resolve("SHELLEY_CVMFS_PATH", CVMFS_GALAXY_SINGULARITY_PATH)


def shpc_module_base() -> Path:
    """shpc `module_base` — generated module.lua files."""
    return shpc_base() / "modules"


def shpc_container_base() -> Path:
    """shpc `container_base` — near-empty under `shpc install --keep-path`."""
    return shpc_base() / "containers"


def shpc_wrapper_base() -> Path:
    """shpc `wrapper_base` — the alias wrapper scripts a loaded module puts on PATH."""
    return shpc_base() / "wrappers"


def shpc_views_base() -> Path:
    """shpc `views_base` — unused by shelley, created so `shpc view` stays usable."""
    return shpc_base() / "views"


def shpc_settings_file() -> Path:
    """The shelley-managed shpc settings file passed as `--settings-file`."""
    return shpc_base() / "settings.yml"


def shared_dirs() -> tuple[Path, ...]:
    """Every directory the shared build layout needs, parents before children."""
    return (
        shpc_base(),
        shpc_module_base(),
        shpc_container_base(),
        shpc_wrapper_base(),
        shpc_views_base(),
        local_registry(),
        lmod_modules(),
    )


def build_roots() -> tuple[Path, ...]:
    """The three prefixes a build must be able to write to."""
    return (shpc_base(), local_registry(), lmod_modules())
