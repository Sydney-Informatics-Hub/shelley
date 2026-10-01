"""Build command — install Lmod modules from CVMFS."""

import importlib.util
import os
import re
import shutil
import subprocess
import sys

from ..builder.cvmfs_builder import CVMFSModuleBuilder
from ..builder.shpc_settings import ensure_shared_shpc_settings
from ..utils.globals import build_roots
from ..utils.modules import load_build_modules
from ..utils.perms import apply_build_umask, ensure_shared_layout
from ..utils.style import (
    ShelleyStyle,
    console,
    print_error,
    print_info,
    print_rule,
    print_warning,
)


def needs_sudo() -> bool:
    """Return True if this process cannot write everywhere a build needs to.

    All three shared roots are checked, not just the modulefiles directory: on a fresh
    machine /apps/shpc and /apps/local do not exist yet and creating them needs root.
    A missing root counts as needing sudo — if we cannot see it, we certainly cannot
    create it in place.
    """
    if os.geteuid() == 0:
        return False
    return any(
        not root.exists() or not os.access(root, os.W_OK) for root in build_roots()
    )


def sudo_env_args() -> list[str]:
    """Environment assignments to hand to `sudo env` for the elevated re-exec.

    PATH so the shelley launcher and shpc stay findable, and any SHELLEY_* override so
    the elevated child agrees with us about where to build. `sudo -E` should preserve
    them already, but it requires SETENV privilege and sudoers policy can deny it.
    """
    args = [f"PATH={os.environ['PATH']}"]
    args += [
        f"{k}={v}" for k, v in sorted(os.environ.items()) if k.startswith("SHELLEY_")
    ]
    return args


def resolve_shelley_executable() -> str | None:
    """Locate an installed `shelley` launcher on PATH.

    Fallback only — see reexec_command, which prefers the running interpreter. We rely on
    PATH rather than deriving a path from __file__, because the launcher and the package
    live in unrelated directories under a `uv tool install` layout (the launcher is in
    .../uv/tools/shelley/bin/, the package in .../site-packages/shelley/).
    """
    return shutil.which("shelley")


def reexec_command() -> list[str] | None:
    """Return the argv prefix that re-invokes *this* shelley under sudo.

    `sys.executable -m shelley` re-runs the exact package that is running now. A PATH
    lookup cannot guarantee that: with a system-wide shelley installed, `uv run shelley
    build` in a checkout would re-exec the *system* copy for the privileged half of the
    build, so the elevated process — the one that actually installs — could be a
    different, older version. That failure is near-invisible: the unprivileged half
    prints the new version's output while the build itself behaves like the old one.

    Falls back to a PATH lookup only if this package is somehow not importable by name,
    which should not happen since we are executing from inside it.
    """
    if importlib.util.find_spec("shelley") is not None:
        return [sys.executable, "-m", "shelley"]

    launcher = resolve_shelley_executable()
    return [launcher] if launcher else None


def build_module(tool_spec: str, interactive: bool = False) -> bool:
    """Build an Lmod module for a tool from CVMFS.

    ``interactive`` opens a session to curate the aliases the module exposes —
    deselect, rename, and add — for both upstream and local builds.

    Returns True if the build succeeded, False otherwise.
    """
    if needs_sudo():
        # Re-invoke this same shelley with sudo, preserving PATH so shpc stays findable.
        launcher = reexec_command()
        if launcher is None:
            print_error("Could not locate the 'shelley' executable on PATH")
            return False

        cmd = [
            "sudo",
            "-E",
            "env",
            *sudo_env_args(),
            *launcher,
            "build",
            tool_spec,
        ]
        if interactive:
            cmd.append("--interactive")

        try:
            print_info(f"Running with elevated privileges: build {tool_spec}")
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print_error(f"Build failed with exit code {result.returncode}")
                return False
            return True
        except subprocess.CalledProcessError as e:
            print_error(f"Build command failed: {e}")
            return False
        except KeyboardInterrupt:
            print_warning("Build cancelled by user")
            return False

    # Set the umask before anything forks. sudo unions the caller's umask with the
    # sudoers default, so without this a user with `umask 077` produces 0700 directories
    # under /apps that no other user can enter. Deliberately not done at import time:
    # the umask is process-global and read-only commands must not touch it.
    apply_build_umask()

    # Load shpc + singularity here (not in CVMFSModuleBuilder.__init__) so it only
    # happens on the build path. This runs in whichever process actually performs the
    # install — including the elevated child after the sudo re-exec above — rather than
    # relying on `sudo -E` preserving the Lmod environment.
    load_build_modules()

    # Bootstrap the shared layout before the settings file names the local registry:
    # shpc raises on a registry path that does not exist.
    try:
        ensure_shared_layout()
        ensure_shared_shpc_settings()
    except (OSError, RuntimeError) as e:
        console.print(
            ShelleyStyle.create_error_panel(
                title="Build Failed",
                message=str(e),
                suggestion="Check write access to the shared build directories, or set "
                "SHELLEY_SHPC_BASE to a writable location",
            )
        )
        return False

    builder = CVMFSModuleBuilder()

    try:
        if "/" in tool_spec:
            tool_name, requested_version = tool_spec.split("/", 1)
        elif ":" in tool_spec:
            tool_name, requested_version = tool_spec.split(":", 1)
        else:
            tool_name, requested_version = tool_spec, None

        final_tool, final_version = builder.search_tool_version(
            tool_name, requested_version
        )

        with ShelleyStyle.create_status(f"Building module for {tool_spec}") as status:
            module_file = builder.shpc_install(
                final_tool,
                final_version,
                interactive=interactive,
                status=status,
            )
            available_versions = builder.list_versions(tool_name)

        if requested_version is None and len(available_versions) > 1:
            console.print(
                ShelleyStyle.create_build_info(
                    final_tool, final_version, available_versions
                )
            )
            print_rule()

        console.print(
            ShelleyStyle.create_build_success(final_tool, final_version, module_file)
        )
        return True

    except Exception as e:
        title = "Build Failed"
        msg = str(e)
        suggestion = "Check that CVMFS is mounted and the tool exists"

        if re.search(r"^Version .* not found for", msg):
            suggestion = ""

        console.print(
            ShelleyStyle.create_error_panel(
                title=title, message=msg, suggestion=suggestion
            )
        )
        return False


def list_cvmfs_versions(tool_name: str) -> None:
    """List available versions of a tool by scanning CVMFS directly."""
    builder = CVMFSModuleBuilder()

    try:
        with ShelleyStyle.create_status(
            f"Scanning CVMFS for {tool_name} versions"
        ):
            version_path_pairs = builder.list_versions_with_paths(tool_name)

        if not version_path_pairs:
            console.print(
                ShelleyStyle.create_error_panel(
                    "No Versions Found",
                    f"No versions of '{tool_name}' found in CVMFS",
                    "Check the tool name spelling or try a different tool",
                )
            )
        else:
            console.print(
                ShelleyStyle.create_versions_with_paths_table(
                    tool_name, version_path_pairs
                )
            )

    except Exception as e:
        console.print(
            ShelleyStyle.create_error_panel(
                "CVMFS Access Error",
                str(e),
                "Ensure CVMFS is mounted at /cvmfs/singularity.galaxyproject.org/",
            )
        )
