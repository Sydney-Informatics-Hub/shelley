"""Ensures build artefacts that cancelled or failed are removed

``BuildTransaction`` is a context manager around the writes of one build:

- On entry it takes a per-tool lock, so two builds of the same tool cannot interleave,
  and records a *pre-image* of the tool's directories (``ShpcExposer.tool_dirs``):
  every path's type, mode, symlink
  target and (small) file bytes.
- Unless ``commit()`` is called before the block ends, it restores that pre-image
  exactly: new paths are deleted, changed ones are rewritten, and modes are reset.
- ``on_commit`` callbacks run only after a commit, e.g. to delete moved-aside copies.

Tool directories hold small text files only: ``shpc install --keep-path`` leaves the SIF on CVMFS.
"""

import fcntl
import os
import shutil
import stat
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from .errors import ShelleyError
from .utils import globals as gl
from .utils.globals import SHARED_DIR_MODE, SHARED_FILE_MODE

LOCK_TIMEOUT = 300.0  # seconds to wait for another build of the same tool


class BuildInProgress(ShelleyError):
    def __init__(self, tool: str, waited: float):
        self.tool = tool
        super().__init__(
            f"Another build of '{tool}' is still running (waited {waited:g} s). "
            "Try again when it has finished."
        )


class RollbackFailed(ShelleyError):
    def __init__(self, cause: BaseException, error: BaseException):
        self.cause, self.error = cause, error
        super().__init__(
            f"The build failed ({cause}) and undoing it also failed ({error}). "
            "Some files under the shared build directories may need removing by hand."
        )


@dataclass(frozen=True)
class _Node:
    kind: str  # "dir", "file" or "link"
    mode: int | None
    payload: bytes | str | None  # file bytes or link target


class PreImage:
    """The exact state of some directories (and their ancestors inside the build roots)."""

    def __init__(self, tool_dirs: Iterable[Path], roots: Iterable[Path]):
        self.tool_dirs = [Path(p) for p in tool_dirs]
        self.roots = [Path(r) for r in roots]
        self.nodes: dict[Path, _Node] = {}
        for top in self.tool_dirs:
            for ancestor in self._ancestors(top):
                if ancestor.is_dir() and not ancestor.is_symlink():
                    self.nodes.setdefault(ancestor, self._node(ancestor))
            if top.is_symlink() or top.is_file():
                self.nodes[top] = self._node(top)
                continue
            if not top.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
                for name in dirnames + filenames:
                    p = Path(dirpath) / name
                    self.nodes[p] = self._node(p)

    def _ancestors(self, top: Path) -> list[Path]:
        """``top`` and its parents, up to and including its build root."""
        root = next((r for r in self.roots if r == top or r in top.parents), None)
        if root is None:
            raise ValueError(f"{top} is outside every build root")
        chain, p = [], top
        while True:
            chain.append(p)
            if p == root:
                return chain
            p = p.parent

    @staticmethod
    def _node(p: Path) -> _Node:
        st = p.lstat()
        if stat.S_ISLNK(st.st_mode):
            return _Node("link", None, os.readlink(p))
        if stat.S_ISDIR(st.st_mode):
            return _Node("dir", stat.S_IMODE(st.st_mode), None)
        return _Node("file", stat.S_IMODE(st.st_mode), p.read_bytes())

    def restore(self) -> None:
        # 1. Delete what is new: anything under a tool directory, or a moved-aside sibling.
        for top in self.tool_dirs:
            self._remove_new(top)
            if top.parent.is_dir():
                for sibling in top.parent.iterdir():
                    if sibling.name.endswith(".aside") and sibling not in self.nodes:
                        _remove(sibling)
        # 2. Remove new, now-empty ancestors (e.g. intermediates created by shpc).
        for top in self.tool_dirs:
            for p in self._ancestors(top):
                if p not in self.nodes and p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
        # 3. Recreate what is missing or changed, parents first; reset modes.
        for p, node in sorted(self.nodes.items(), key=lambda kv: len(kv[0].parts)):
            if node.kind == "dir":
                if p.is_symlink() or (p.exists() and not p.is_dir()):
                    p.unlink()
                p.mkdir(exist_ok=True)
            elif node.kind == "link":
                if not (p.is_symlink() and os.readlink(p) == node.payload):
                    _remove(p)
                    p.symlink_to(node.payload)
            else:
                if p.is_symlink() or p.is_dir():
                    _remove(p)
                if not p.is_file() or p.read_bytes() != node.payload:
                    p.write_bytes(node.payload)  # type: ignore[arg-type]
            if node.mode is not None:
                os.chmod(p, node.mode)

    def _remove_new(self, top: Path) -> None:
        if not (top.exists() or top.is_symlink()):
            return
        if top not in self.nodes:
            _remove(top)
            return
        if top.is_dir() and not top.is_symlink():
            for dirpath, dirnames, filenames in os.walk(top, topdown=False):
                for name in filenames + dirnames:
                    p = Path(dirpath) / name
                    if p not in self.nodes and (p.exists() or p.is_symlink()):
                        _remove(p)


def _remove(p: Path) -> None:
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    elif p.exists() or p.is_symlink():
        p.unlink()


class BuildTransaction:
    """``with BuildTransaction(tool, tool_dirs) as tx: ...; tx.commit()``"""

    def __init__(
        self,
        tool: str,
        tool_dirs: Iterable[Path],
        roots: Iterable[Path] | None = None,
        lock_dir: Path | None = None,
        lock_timeout: float = LOCK_TIMEOUT,
    ):
        self.tool = tool
        self.tool_dirs = list(tool_dirs)
        self.roots = list(roots) if roots is not None else list(gl.build_roots())
        self.lock_dir = lock_dir if lock_dir is not None else gl.shpc_base() / ".locks"
        self.lock_timeout = lock_timeout
        self.committed = False
        self._on_commit: list[Callable[[], None]] = []
        self._lock_fd: int | None = None
        self._pre: PreImage | None = None

    def on_commit(self, callback: Callable[[], None]) -> None:
        self._on_commit.append(callback)

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> "BuildTransaction":
        self._acquire_lock()
        try:
            self._pre = PreImage(self.tool_dirs, self.roots)
        except BaseException:
            self._release_lock()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if self.committed and exc is None:
                for callback in self._on_commit:
                    callback()
                return False
            assert self._pre is not None
            try:
                self._pre.restore()
            except Exception as restore_error:
                cause = exc or RuntimeError("transaction ended without commit")
                raise RollbackFailed(cause, restore_error) from restore_error
            return False  # re-raise the original exception, if any
        finally:
            self._release_lock()

    def _acquire_lock(self) -> None:
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.lock_dir, SHARED_DIR_MODE)
        path = self.lock_dir / f"{self.tool}.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT, SHARED_FILE_MODE)
        start = time.monotonic()
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._lock_fd = fd
                return
            except BlockingIOError:
                waited = time.monotonic() - start
                if waited >= self.lock_timeout:
                    os.close(fd)
                    raise BuildInProgress(self.tool, round(waited)) from None
                time.sleep(min(0.5, self.lock_timeout))

    def _release_lock(self) -> None:
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None
