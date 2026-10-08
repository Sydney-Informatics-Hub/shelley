"""HTTP fetches that tell "not there" apart from "couldn't reach it" (ADR 0004).

``fetch_text`` returns the body, ``None`` for HTTP 404 (the resource does not exist),
and raises ``NetworkUnavailable`` with a plain-language reason for everything else. A
build calls it before writing anything, so an outage stops the build cleanly instead of
being mistaken for "not in the upstream registry".

Uses urllib, which honours ``http(s)_proxy`` like curl did.
"""

import os
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..errors import NetworkUnavailable

TIMEOUT = 10.0  # seconds; quoted in the message, e.g. "timed out after 10 s"


@dataclass(frozen=True)
class Reachability:
    ok: bool
    host: str
    reason: str = ""


def fetch_text(url: str, timeout: float = TIMEOUT) -> str | None:
    """GET ``url`` and return its body; ``None`` on 404; raise ``NetworkUnavailable`` otherwise."""
    host = urlsplit(url).hostname or url
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise NetworkUnavailable(host, f"the server returned HTTP {e.code}") from e
    except (urllib.error.URLError, OSError) as e:
        raise NetworkUnavailable(host, describe(e, timeout)) from e


def diagnose(url: str, timeout: float = TIMEOUT) -> Reachability:
    """Whether ``url``'s host is reachable now, with the reason if not."""
    host = urlsplit(url).hostname or url
    try:
        fetch_text(url, timeout)
    except NetworkUnavailable as e:
        return Reachability(False, host, e.reason)
    return Reachability(True, host)


def describe(error: BaseException, timeout: float = TIMEOUT) -> str:
    """A short, plain-language reason for a failed request."""
    cause = getattr(error, "reason", error)  # URLError wraps the socket error
    if isinstance(cause, socket.gaierror):
        return "the name could not be resolved (no DNS or no network)"
    if isinstance(cause, TimeoutError | socket.timeout):
        return f"the request timed out after {timeout:g} s"
    if isinstance(cause, ConnectionRefusedError):
        if _proxy_configured():
            return "the proxy refused the connection"
        return "the connection was refused"
    if isinstance(cause, ssl.SSLError):
        return "a secure connection could not be established"
    if isinstance(cause, OSError) and cause.strerror:
        return cause.strerror[0].lower() + cause.strerror[1:]
    return str(cause) or type(cause).__name__


def _proxy_configured() -> bool:
    return any(
        os.environ.get(k)
        for k in ("https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")
    )
