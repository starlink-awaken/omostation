"""Minerva test helpers."""

import os
import shutil
import socket
import urllib.error
import urllib.request


def _has_network(timeout: float = 2.0) -> bool:
    """Check if network connectivity is available by attempting to reach common endpoints."""
    hosts = [
        ("1.1.1.1", 53, "udp"),  # Cloudflare DNS (UDP)
        ("8.8.8.8", 53, "udp"),  # Google DNS (UDP)
    ]
    for host, port, proto in hosts:
        try:
            if proto == "udp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                sock.sendto(b"\x00", (host, port))
                sock.close()
                return True
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((host, port))
                sock.close()
                return True
        except OSError:
            continue
    # Fallback: try an HTTP HEAD request
    try:
        urllib.request.urlopen("https://1.1.1.1", timeout=timeout)
        return True
    except (urllib.error.URLError, OSError):
        pass
    return False


def _has_api_key(key: str = "OPENAI_API_KEY") -> bool:
    """Check if a required API key environment variable is set."""
    return bool(os.environ.get(key))


def _has_module(name: str) -> bool:
    """Check if a Python module is importable."""
    import importlib

    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


# Reusable skip conditions
requires_api_key = os.environ.get("OPENAI_API_KEY") is None
requires_sophia = not _has_module("sophia") and not shutil.which("sophia")
requires_network = not _has_network()
