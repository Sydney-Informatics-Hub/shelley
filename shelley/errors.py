"""Typed failures for the build core.

Each one names a distinct situation the user can act on, so callers never have to tell
"not found" from "couldn't check" by inspecting an empty result (ADR 0004). Messages
are written for the user; the attributes carry the detail for callers and tests.
"""

from collections.abc import Sequence
from pathlib import Path


class ShelleyError(Exception):
    """Base class for errors that shelley reports to the user as-is."""


class TagNotFound(ShelleyError):
    """The tool, or the requested version of it, does not exist in the supplier."""

    def __init__(self, tool: str, requested: str | None, available: Sequence[str] = ()):
        self.tool, self.requested, self.available = tool, requested, list(available)
        if requested is None:
            message = f"'{tool}' not found in Galaxy CVMFS."
        else:
            message = f"Version '{requested}' not found for '{tool}'."
        if self.available:
            message += f" Available versions: {', '.join(self.available)}"
        super().__init__(message)


class AmbiguousTag(ShelleyError):
    """A requested version matches several container builds; one must be chosen."""

    def __init__(self, tool: str, requested: str, matches: Sequence[str]):
        self.tool, self.requested, self.matches = tool, requested, list(matches)
        super().__init__(
            f"'{requested}' matches {len(self.matches)} builds of '{tool}': "
            f"{', '.join(self.matches)}. Specify the full tag."
        )


class TagRequired(ShelleyError):
    """The tool's tags carry no version order (mulled containers), so "latest" is undefined."""

    def __init__(self, tool: str, available: Sequence[str]):
        self.tool, self.available = tool, list(available)
        super().__init__(
            f"'{tool}' is a multi-tool container whose tags have no version order. "
            f"Specify a tag: {', '.join(self.available)}"
        )


class MountUnavailable(ShelleyError):
    """The supplier's CVMFS directory is not mounted or not readable."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Galaxy CVMFS is not mounted at {path}.")


class NetworkUnavailable(ShelleyError):
    """A remote service could not be reached; nothing was changed.

    ``reason`` is a plain-language clause such as "the request timed out after 10 s".
    """

    def __init__(self, host: str, reason: str, service: str | None = None):
        self.host, self.reason = host, reason
        self.service = service or _service_name(host)
        super().__init__(
            f"Couldn't reach {self.service} ({host}): {reason}. "
            "Try again in a few seconds."
        )


def _service_name(host: str) -> str:
    """A name a user recognises for the hosts shelley talks to."""
    if (
        host == "github.com"
        or host.endswith(".github.com")
        or host.endswith(".githubusercontent.com")
    ):
        return "GitHub"
    return host
