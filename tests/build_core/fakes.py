"""Mock fixtures for edge case tests of the build path, with no shpc, network or root needed."""

from pathlib import Path

from shelley.errors import NetworkUnavailable
from shelley.tools.shpc import ShpcFailed
from shelley.utils import globals as gl

UPSTREAM_SAMTOOLS = {
    "docker": "quay.io/biocontainers/samtools",
    "latest": {"1.21--h50ea8bc_3": "sha256:aaa"},
    "tags": {"1.21--h50ea8bc_3": "sha256:aaa", "1.10--h2e538c0_3": "sha256:bbb"},
    "maintainer": "@vsoch",
    "description": "samtools",
    "aliases": {"samtools": "/usr/local/bin/samtools"},
}


class FakeShpc:
    """Creates what ``shpc install --keep-path`` creates (observed in the batch 0 spike)."""

    def __init__(self, fail_on: str | None = None):
        self.calls: list[tuple] = []
        self.fail_on = fail_on

    def install(self, uri_tag: str, sif: Path) -> None:
        self.calls.append(("install", uri_tag, sif))
        uri, tag = uri_tag.rsplit(":", 1)
        module_dir = gl.shpc_module_base() / uri / tag
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "module.lua").write_text(f"-- {uri_tag}\n")
        (gl.shpc_module_base() / uri / ".version").write_text(
            '#%Module\nset ModulesVersion "please_specify_a_version_number"\n'
        )
        wrappers = gl.shpc_wrapper_base() / uri / tag
        (wrappers / "bin").mkdir(parents=True, exist_ok=True)
        (wrappers / "99-shpc.sh").write_text("#!/bin/sh\n")
        tool = uri.rsplit("/", 1)[1]
        script = wrappers / "bin" / tool
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        (gl.shpc_container_base() / uri / tag).mkdir(parents=True, exist_ok=True)
        if self.fail_on == "install":
            raise ShpcFailed("install", uri_tag, "injected failure after writing")

    def uninstall(self, uri_tag: str) -> None:
        self.calls.append(("uninstall", uri_tag))

    def module_base(self) -> Path:
        return gl.shpc_module_base()


class FakeRegistry:
    """Upstream registry: a dict of entries, or unreachable."""

    def __init__(self, entries: dict | None = None, reachable: bool = True):
        self.entries = entries or {}
        self.reachable = reachable
        self.calls: list[str] = []

    def fetch(self, uri: str) -> dict | None:
        self.calls.append(uri)
        if not self.reachable:
            raise NetworkUnavailable(
                "raw.githubusercontent.com", "the request timed out after 10 s"
            )
        return self.entries.get(uri)
