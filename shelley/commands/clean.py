"""Clean command — uninstall a specific tool@version. Inverse of `shelley build`."""

import subprocess

import questionary
from rich.panel import Panel

from ..builder.cvmfs_builder import CVMFSModuleBuilder
from ..commands.build import needs_sudo, reexec_command, sudo_env_args
from ..commands.find import list_installed_versions
from ..utils.modules import load_build_modules
from ..utils.perms import apply_build_umask
from ..utils.style import console, ShelleyStyle, print_info, print_warning, print_error


def _parse_tool_spec(tool_spec: str) -> tuple[str, str | None]:
    """Split '<tool>:<version>' or '<tool>/<version>' (both separators, like build)."""
    if "/" in tool_spec:
        tool_name, version = tool_spec.split("/", 1)
    elif ":" in tool_spec:
        tool_name, version = tool_spec.split(":", 1)
    else:
        tool_name, version = tool_spec, None
    return tool_name, version


def _resolve_installed_version(tool_name: str, version_spec: str) -> str:
    """Match version_spec (full or short) against installed modulefiles for tool_name.

    Mirrors the short/full version matching used at build time (e.g. "1.21" matching
    "1.21--h96c455f_1"), but against what is actually installed rather than what CVMFS
    has available — clean has no reason to require CVMFS to be mounted.

    Raises ValueError when there is no match, or more than one (an ambiguous short
    version with two installed hash-suffixed builds).
    """
    installed = list_installed_versions(tool_name)
    matches = [v for v in installed if v == version_spec or v.split("--", 1)[0] == version_spec]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"Version '{version_spec}' is not installed for '{tool_name}'.")
    raise ValueError(
        f"'{version_spec}' matches more than one installed build of '{tool_name}': "
        f"{', '.join(matches)}. Specify the full version string."
    )


def _not_installed_panel(
    tool_name: str, requested_version: str | None, detail: str | None = None,
) -> Panel:
    """Error panel for 'no version given' and 'version not installed', listing what is."""
    installed = list_installed_versions(tool_name)
    if installed:
        versions_text = "\n".join(f"  • {v}" for v in installed)
        suggestion = (
            f"Currently installed versions of '{tool_name}':\n{versions_text}\n\n"
            f"Re-run with one of these, e.g.:\n"
            f"shelley clean {tool_name}:{installed[0]}"
        )
    else:
        suggestion = f"'{tool_name}' has no installed versions to clean."

    if requested_version is None:
        message = f"shelley clean requires an explicit version, e.g. {tool_name}:<version>."
    else:
        message = detail or f"Version '{requested_version}' is not installed for '{tool_name}'."

    return ShelleyStyle.create_error_panel("Not Installed", message, suggestion)


def clean_module(tool_spec: str, force: bool = False) -> bool:
    """Uninstall a specific tool@version. Requires an explicit version.

    Confirms interactively before deleting anything, unless force=True (the -y
    flag). Version resolution and the confirmation prompt both happen before any
    sudo re-exec, so a bad/ambiguous/missing version is reported without ever
    asking for a password, and the confirmation runs in the process attached to
    the user's terminal rather than racing sudo's own prompt on the same TTY. The
    re-exec'd child is always invoked with -y, since confirmation already
    happened in the parent.

    Returns True if tool@version was cleaned, False on error or user decline.
    """
    tool_name, requested_version = _parse_tool_spec(tool_spec)

    if requested_version is None:
        console.print(_not_installed_panel(tool_name, None))
        return False

    try:
        version = _resolve_installed_version(tool_name, requested_version)
    except ValueError as e:
        console.print(_not_installed_panel(tool_name, requested_version, str(e)))
        return False

    if not force:
        confirmed = questionary.confirm(
            f"Remove {tool_name}/{version}? This deletes its module, wrappers, "
            "and container artifacts.",
            default=False,
        ).ask()
        if not confirmed:
            print_warning("Clean cancelled; nothing was removed.")
            return False

    if needs_sudo():
        launcher = reexec_command()
        if launcher is None:
            print_error("Could not locate the 'shelley' executable on PATH")
            return False

        cmd = [
            "sudo", "-E", "env", *sudo_env_args(),
            *launcher, "clean", f"{tool_name}:{version}", "-y",
        ]
        try:
            print_info(f"Running with elevated privileges: clean {tool_name}:{version}")
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print_error(f"Clean failed with exit code {result.returncode}")
                return False
            return True
        except KeyboardInterrupt:
            print_warning("Clean cancelled by user")
            return False

    apply_build_umask()
    load_build_modules()

    builder = CVMFSModuleBuilder()
    try:
        with ShelleyStyle.create_status(f"Removing {tool_name}/{version}"):
            report = builder.uninstall_module(tool_name, version)
    except OSError as e:
        console.print(ShelleyStyle.create_error_panel(
            "Clean Failed", str(e),
            "Check write access to the shared build directories",
        ))
        return False

    if not report["shpc_removed"]:
        console.print(ShelleyStyle.create_warning_panel(
            "shpc uninstall reported an issue",
            f"{report['uri_tag']}: {(report['shpc_output'] or '').strip() or 'non-zero exit'} "
            "— the Lmod modulefile symlink was still cleaned up.",
        ))

    console.print(ShelleyStyle.create_clean_success(tool_name, version, report))
    return True
