"""BuildTransaction: exact restore unless committed, and a per-tool lock to
prevent multi-user clashes"""

import subprocess
import sys
import time

import pytest

from shelley.transaction import (
    BuildInProgress,
    BuildTransaction,
    PreImage,
    RollbackFailed,
)
from shelley.utils import globals as gl

from .roots_snapshot import changes, snapshot


@pytest.fixture
def tool_dirs():
    """An installed-looking tool's directories: files with modes, a symlink."""
    uri = "quay.io/biocontainers/samtools"
    mods = gl.shpc_module_base() / uri
    (mods / "1.10").mkdir(parents=True)
    (mods / "1.10" / "module.lua").write_text("old\n")
    (mods / ".version").write_text("v\n")
    link_dir = gl.lmod_modules() / "samtools"
    link_dir.mkdir(parents=True)
    (link_dir / "1.10.lua").symlink_to(mods / "1.10" / "module.lua")
    return [mods, gl.shpc_wrapper_base() / uri, gl.local_registry() / uri, link_dir]


def _roots():
    return [gl.shpc_base(), gl.local_registry(), gl.lmod_modules()]


def _mess_up(tool_dirs):
    mods, wrappers, registry, links = tool_dirs
    (mods / "1.10" / "module.lua").write_text("changed\n")  # changed bytes
    (mods / ".version").chmod(0o600)  # changed mode
    (mods / "1.21").mkdir()  # new dir
    (mods / "1.21" / "module.lua").write_text("new\n")
    (wrappers / "1.21" / "bin").mkdir(parents=True)  # new dir with new ancestors
    registry.mkdir(parents=True)
    (registry / "container.yaml").write_text("tags: {}\n")
    (links / "1.10.lua").unlink()  # removed link
    (links / "1.10.lua").symlink_to("/elsewhere")


def test_exception_restores_everything(tool_dirs):
    before = snapshot(*_roots())
    with pytest.raises(RuntimeError, match="boom"):
        with BuildTransaction("samtools", tool_dirs):
            _mess_up(tool_dirs)
            raise RuntimeError("boom")
    assert changes(before, snapshot(*_roots())) == []


def test_leaving_without_commit_restores_everything(tool_dirs):
    before = snapshot(*_roots())
    with BuildTransaction("samtools", tool_dirs):
        _mess_up(tool_dirs)
    assert changes(before, snapshot(*_roots())) == []


def test_commit_keeps_changes_and_runs_callbacks(tool_dirs):
    ran = []
    with BuildTransaction("samtools", tool_dirs) as tx:
        _mess_up(tool_dirs)
        tx.on_commit(lambda: ran.append("cleanup"))
        tx.commit()
    assert (tool_dirs[0] / "1.21" / "module.lua").read_text() == "new\n"
    assert ran == ["cleanup"]


def test_callbacks_do_not_run_without_commit(tool_dirs):
    ran = []
    with BuildTransaction("samtools", tool_dirs) as tx:
        tx.on_commit(lambda: ran.append("cleanup"))
    assert ran == []


def test_moved_aside_siblings_are_removed_on_restore(tool_dirs):
    mods = tool_dirs[0]
    before = snapshot(*_roots())
    with BuildTransaction("samtools", tool_dirs):
        (mods / "1.10").rename(mods / "1.10.aside")
    assert changes(before, snapshot(*_roots())) == []


def test_failed_restore_is_reported(tool_dirs, monkeypatch):
    def broken(self):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(PreImage, "restore", broken)
    with pytest.raises(RollbackFailed) as exc:
        with BuildTransaction("samtools", tool_dirs):
            raise RuntimeError("install failed")
    assert "install failed" in str(exc.value) and "No space left" in str(exc.value)


def test_tool_dir_outside_the_build_roots_is_refused(tmp_path):
    with pytest.raises(ValueError, match="outside every build root"):
        with BuildTransaction("x", [tmp_path / "elsewhere"]):
            pass


def test_a_second_build_of_the_same_tool_waits_then_gives_up(tool_dirs):
    lock = gl.shpc_base() / ".locks" / "samtools.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl, sys, time; f = open(sys.argv[1], 'a'); "
            "fcntl.flock(f, fcntl.LOCK_EX); print('held', flush=True); time.sleep(30)",
            str(lock),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        start = time.monotonic()
        with pytest.raises(BuildInProgress, match="Another build of 'samtools'"):
            with BuildTransaction("samtools", tool_dirs, lock_timeout=1):
                pass
        assert time.monotonic() - start >= 1
    finally:
        holder.kill()
        holder.wait()
    with BuildTransaction("samtools", tool_dirs) as tx:  # free again
        tx.commit()


def test_other_tools_are_not_blocked(tool_dirs):
    with BuildTransaction("samtools", tool_dirs) as outer:
        other = [gl.shpc_module_base() / "quay.io/biocontainers/bwa"]
        with BuildTransaction("bwa", other, lock_timeout=0.1) as inner:
            inner.commit()
        outer.commit()
