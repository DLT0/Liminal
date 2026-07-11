"""Network connectivity helpers."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

_USER_AGENT = "Liminal/1.0"
_TIMEOUT = 5

# Lightweight endpoints commonly used for captive-portal / connectivity checks.
_CHECK_URLS = (
    "https://connectivitycheck.gstatic.com/generate_204",
    "https://www.google.com/generate_204",
    "https://www.youtube.com",
    "https://1.1.1.1/cdn-cgi/trace",
)


def is_network_available() -> bool:
    """Return True if the device appears to have general internet access."""
    for url in _CHECK_URLS:
        if _probe_url(url):
            return True
    return _probe_tcp("1.1.1.1", 53) or _probe_tcp("8.8.8.8", 53)


def _probe_url(url: str) -> bool:
    try:
        req = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as exc:
        # Reachable host — treat 4xx as online (blocked but connected).
        return exc.code < 500
    except Exception:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.status < 500
        except urllib.error.HTTPError as exc:
            return exc.code < 500
        except Exception:
            return False


def _probe_tcp(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=_TIMEOUT):
            return True
    except OSError:
        return False
