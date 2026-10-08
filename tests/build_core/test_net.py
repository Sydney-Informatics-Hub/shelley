"""Network failures are named, never mistaken for "not found" (ADR 0004)."""

import socket
import urllib.error
from io import BytesIO

import pytest

from shelley.errors import NetworkUnavailable
from shelley.tools import net

URL = "https://raw.githubusercontent.com/singularityhub/shpc-registry/main/x/container.yaml"


def _raising(exc):
    def urlopen(*args, **kwargs):
        raise exc

    return urlopen


def test_message_matches_the_agreed_wording():
    err = NetworkUnavailable(
        "raw.githubusercontent.com", "the request timed out after 10 s"
    )
    assert str(err) == (
        "Couldn't reach GitHub (raw.githubusercontent.com): "
        "the request timed out after 10 s. Try again in a few seconds."
    )


def test_404_means_not_there(monkeypatch):
    monkeypatch.setattr(
        net.urllib.request,
        "urlopen",
        _raising(urllib.error.HTTPError(URL, 404, "Not Found", {}, BytesIO())),
    )
    assert net.fetch_text(URL) is None


def test_server_error_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        net.urllib.request,
        "urlopen",
        _raising(urllib.error.HTTPError(URL, 503, "Unavailable", {}, BytesIO())),
    )
    with pytest.raises(NetworkUnavailable, match="HTTP 503"):
        net.fetch_text(URL)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            urllib.error.URLError(socket.gaierror(-3, "Temporary failure")),
            "could not be resolved",
        ),
        (urllib.error.URLError(TimeoutError()), "timed out after 10 s"),
        (TimeoutError("read timed out"), "timed out after 10 s"),
        (
            urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")),
            "connection was refused",
        ),
    ],
)
def test_failures_have_plain_reasons(monkeypatch, error, reason):
    for k in ("https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(net.urllib.request, "urlopen", _raising(error))
    with pytest.raises(NetworkUnavailable) as exc:
        net.fetch_text(URL)
    assert reason in exc.value.reason
    assert exc.value.host == "raw.githubusercontent.com"
    assert exc.value.service == "GitHub"


def test_dead_proxy_is_reported_as_the_proxy(monkeypatch):
    """No real network needed: nothing listens on 127.0.0.1:9 (the discard port)."""
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    with pytest.raises(NetworkUnavailable) as exc:
        net.fetch_text(URL, timeout=2)
    assert exc.value.reason == "the proxy refused the connection"


def test_diagnose(monkeypatch):
    monkeypatch.setattr(
        net.urllib.request, "urlopen", _raising(urllib.error.URLError(TimeoutError()))
    )
    result = net.diagnose(URL)
    assert not result.ok and "timed out" in result.reason
