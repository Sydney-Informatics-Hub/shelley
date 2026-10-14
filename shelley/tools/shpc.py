"""A wrapper for shpc

Every call pins shelley's shared settings file (``--settings-file``), so shpc never falls
back to its ``$HOME`` defaults under ``sudo -E`` (see ``builder/shpc_settings.py``).
Failures raise ``ShpcFailed`` with shpc's own output, rather than returning exit codes
for callers to check.
"""

import shutil
import subprocess
from pathlib import Path

from ..errors import ShelleyError
from ..utils import globals as gl


class ShpcFailed(ShelleyError):
    def __init__(self, action: str, target: str, output: str):
        self.action, self.target, self.output = action, target, output.strip()
        super().__init__(f"shpc {action} failed for {target}:\n{self.output}")


class Shpc:
    """Runs shpc with the shared settings file."""

    def __init__(self, binary: str | None = None):
        self._binary = binary

    def _argv(self, *args: str) -> list[str]:
        # Resolved per call: shpc only appears on PATH after `module load shpc`.
        binary = self._binary or shutil.which("shpc") or "/opt/shpc/bin/shpc"
        argv = [binary]
        settings = gl.shpc_settings_file()
        if settings.is_file():  # shpc hard-exits on a missing --settings-file
            argv += ["--settings-file", str(settings)]
        return argv + list(args)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(self._argv(*args), capture_output=True, text=True)

    def install(self, uri_tag: str, sif: Path) -> None:
        """``shpc install <uri:tag> <sif> --keep-path``: the SIF stays on CVMFS."""
        r = self._run("install", uri_tag, str(sif), "--keep-path")
        if r.returncode:
            raise ShpcFailed("install", uri_tag, r.stdout + r.stderr)

    def uninstall(self, uri_tag: str) -> None:
        r = self._run("uninstall", "--force", uri_tag)
        if r.returncode:
            raise ShpcFailed("uninstall", uri_tag, r.stdout + r.stderr)

    def module_base(self) -> Path:
        """Where shpc writes modules; the shared default if shpc cannot say."""
        r = self._run("config", "get", "module_base")
        reported = r.stdout.strip() if r.returncode == 0 else ""
        return Path(reported) if reported else gl.shpc_module_base()
