"""Permissions for the shared build layout.

Build artifacts are written by root (the build path re-execs under sudo) but must be
readable and executable by every user on the machine. Two layers get us there:

1. ``apply_build_umask`` — set the process umask before any subprocess runs, so
   everything shpc creates is 0755/0644 from birth. Necessary because sudo unions the
   caller's umask with the sudoers default, so a user with ``umask 077`` would
   otherwise produce 0700 directories inside /apps.
2. ``harden_tree`` — an explicit chmod pass over the subtrees a build touched, for
   directories that already existed under a stricter umask, or were created by a
   direct ``shpc`` call outside shelley.

Everything here is best-effort except ``ensure_shared_dir``, which propagates so that
a failed bootstrap is loud rather than producing a half-shared install.
"""

import logging
import os
import stat
from pathlib import Path

from .globals import (
    SHARED_DIR_MODE,
    SHARED_EXEC_MODE,
    SHARED_FILE_MODE,
    SHARED_UMASK,
    build_roots,
    shared_dirs,
)

log = logging.getLogger(__name__)

# Bits added to make a path readable and traversable by group and other.
_GO_READ_EXEC = 0o055


def apply_build_umask() -> int:
    """Set the process umask for the build and return the previous value.

    Called from the build path only. Do NOT move this to import time: the umask is
    process-global and inherited by every child (shpc, singularity, git, curl), and
    read-only commands like `find` have no business changing it.
    """
    return os.umask(SHARED_UMASK)


def _chmod(path: Path, mode: int) -> None:
    """chmod, tolerating races and paths we do not own."""
    try:
        os.chmod(path, mode)
    except OSError as e:
        log.debug("Could not chmod %s to %o: %s", path, mode, e)


def _enclosing_root(path: Path) -> Path | None:
    """Return the build root containing path, or None if it lies outside all of them.

    Guards every chmod that walks upwards, so we can never touch /, /apps, or a
    user's home no matter what path we are handed.
    """
    for root in build_roots():
        if path == root or root in path.parents:
            return root
    return None


def ensure_shared_dir(path: Path) -> Path:
    """Create path (with parents) and make it world readable/traversable.

    Raises on failure — callers use this for bootstrap, where a silent failure would
    send artifacts somewhere unshared.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    _chmod(path, SHARED_DIR_MODE)
    ensure_traversable(path)
    return path


def ensure_traversable(path: Path) -> None:
    """Make every directory from path up to its build root group/other traversable.

    shpc creates the intermediate `quay.io/`, `biocontainers/` and `<tool>/` levels
    with a bare os.makedirs, so their modes depend on the umask in force at the time.
    A single non-traversable component makes the module.lua below it unreadable.
    """
    path = Path(path)
    root = _enclosing_root(path)
    if root is None:
        log.debug("Refusing to chmod %s: outside every build root", path)
        return

    current = path if path.is_dir() else path.parent
    while True:
        if current.is_dir() and not current.is_symlink():
            try:
                mode = stat.S_IMODE(current.stat().st_mode)
            except OSError as e:
                log.debug("Could not stat %s: %s", current, e)
            else:
                _chmod(current, mode | _GO_READ_EXEC)
        if current == root:
            break
        current = current.parent


def harden_tree(root: Path) -> None:
    """Recursively make root world readable and traversable.

    Equivalent to `chmod -R a+rX,go-w`: directories become 0755, files 0644, and a
    file the owner can execute becomes 0755 — that last case is what preserves the
    executability of shpc's alias wrapper scripts.

    Symlinks are skipped rather than chmodded. os.chmod follows them and
    follow_symlinks=False is unsupported on Linux, so chmodding a link would silently
    modify its target — which for a module tree can mean something in read-only CVMFS
    or outside the shared prefix entirely.
    """
    root = Path(root)
    if not root.exists():
        return

    if root.is_symlink():
        log.debug("Refusing to harden %s: it is a symlink", root)
        return

    _chmod(root, SHARED_DIR_MODE)

    def _onerror(e: OSError) -> None:
        log.debug("Could not walk %s: %s", getattr(e, "filename", "?"), e)

    for dirpath, dirnames, filenames in os.walk(
        root, followlinks=False, onerror=_onerror
    ):
        base = Path(dirpath)
        for name in dirnames:
            child = base / name
            # os.walk still *lists* symlinked directories; it just does not descend.
            if child.is_symlink():
                continue
            _chmod(child, SHARED_DIR_MODE)
        for name in filenames:
            child = base / name
            if child.is_symlink():
                continue
            try:
                owner_exec = bool(child.stat().st_mode & stat.S_IXUSR)
            except OSError as e:
                log.debug("Could not stat %s: %s", child, e)
                continue
            _chmod(child, SHARED_EXEC_MODE if owner_exec else SHARED_FILE_MODE)


def share_file(path: Path) -> None:
    """Make a single file world readable (0644), preserving nothing else."""
    path = Path(path)
    if path.is_symlink() or not path.exists():
        return
    _chmod(path, SHARED_FILE_MODE)


def ensure_shared_layout() -> None:
    """Create the shared build layout with shared modes. Idempotent.

    Order matters: the local registry directory must exist before shelley's settings
    file names it, because shpc raises ValueError for a filesystem registry path that
    does not exist (shpc/main/registry/filesystem.py: Filesystem.matches).
    """
    for path in shared_dirs():
        ensure_shared_dir(path)
