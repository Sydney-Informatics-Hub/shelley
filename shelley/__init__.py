"""
Shelley - A bioinformatics tool finder and module builder

This package provides tools for finding, querying, and building modules for
bioinformatics software from CVMFS repositories.
"""

# Single source of truth for shelley's version. pyproject.toml derives the
# package version from this via [tool.hatch.version], and the runtime update
# check (shelley/utils/update_check.py) compares it against this same value on
# the main branch. To release: bump here, mirror it into CITATION.cff (`version`
# and `date-released` — nothing derives those, so they must be hand-edited or they
# go stale), update CHANGELOG.md, and tag vX.Y.Z.
# See docs/how-to/developer-setup.md ("Preparing a release").
__version__ = "0.3.0-dev"

from .client.cli import main as cli_main
from .builder.cvmfs_builder import CVMFSModuleBuilder

__all__ = ["cli_main", "CVMFSModuleBuilder"]