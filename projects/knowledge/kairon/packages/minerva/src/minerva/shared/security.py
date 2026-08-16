"""Shared security utilities — URL validation, input sanitization."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"})  # noqa: S104

BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fc00::/7"),
]


def is_safe_url(url: str) -> bool:
    """Validate that a URL does not target internal/private network resources.

    Returns False for URLs targeting localhost, private IPs, link-local,
    or cloud metadata endpoints. Returns True for safe public URLs.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in BLOCKED_HOSTS:
        return False
    # Check if hostname is a private IP
    try:
        ip = ipaddress.ip_address(hostname)
        return not any(ip in net for net in BLOCKED_NETWORKS)
    except ValueError:
        pass
    # Hostname is not an IP — resolve and check
    try:
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
        if any(ip in net for net in BLOCKED_NETWORKS):
            return False
    except Exception:
        return False
    return True
