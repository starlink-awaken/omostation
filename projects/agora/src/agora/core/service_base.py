"""Base data classes and helpers for the service registry."""

from __future__ import annotations

import ipaddress
import json
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",  # noqa: S104
        "metadata.google.internal",
    }
)
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("127.0.0.0/8"),
]
KNOWN_PROTOCOLS = frozenset({"mcp", "rest", "grpc", "stdio", "websocket"})


def parse_tags(tags_str: str) -> list[str]:
    """Parse comma-separated tags string into a deduplicated list."""
    return [t.strip() for t in tags_str.split(",") if t.strip()]


def parse_protocol_config(raw: str | dict) -> tuple[dict, str | None]:
    """Parse protocol_config JSON string into dict. Returns (config, error_message)."""
    if isinstance(raw, dict):
        return raw, None
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return {}, str(e)


def is_safe_url(url: str) -> bool:
    """Validate URL does not target internal/private network resources."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
        return True  # Loopback is always safe for local development
    if hostname.lower() in BLOCKED_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return not any(ip in net for net in BLOCKED_NETWORKS)
    except ValueError:
        pass
    try:
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
        return not any(ip in net for net in BLOCKED_NETWORKS)
    except Exception:
        return False


@dataclass
class ServiceConfig:
    """Grouped params for register_service to reduce parameter sprawl."""

    name: str
    description: str = ""
    protocol: str = "mcp"
    protocol_config: dict = field(default_factory=dict)
    mcp_endpoint: str = ""
    health_endpoint: str = ""
    port: int = 0
    tags: str = ""
    command: str = ""
    mcp_args: str = ""


@dataclass
class Service:
    """A registered service capable of MCP, REST, gRPC, or stdio protocols."""

    name: str
    description: str = ""
    protocol: str = "mcp"
    protocol_config: dict = field(default_factory=dict)
    mcp_endpoint: str = ""
    health_endpoint: str = ""
    port: int = 0
    tags: list[str] = field(default_factory=list)
    instances: list[dict] = field(default_factory=list)
    has_auth: bool = False
    has_push_notifications: bool = False
    has_state_transitions: bool = False
    provider_info: dict | None = None
    documentation_url: str = ""
    healthy: bool = True
    last_health_check: float = 0.0
    failure_count: int = 0
    cooldown_until: float = 0.0
    half_open: bool = False
    consecutive_successes: int = 0

    @property
    def is_available(self) -> bool:
        """Service is available if healthy OR cooldown expired (half-open candidate)."""
        if self.healthy:
            return True
        import time

        return time.monotonic() >= self.cooldown_until

    @property
    def circuit_state(self) -> str:
        """CLOSED (normal), OPEN (failed, cooling down), HALF_OPEN (testing)."""
        if self.healthy:
            return "CLOSED"
        if self.half_open:
            return "HALF_OPEN"
        return "OPEN"

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "description": self.description,
            "protocol": self.protocol,
            "protocol_config": self.protocol_config,
            "healthy": self.is_available,
            "endpoint": self.mcp_endpoint,
            "port": self.port,
            "tags": self.tags,
            "has_auth": self.has_auth,
            "has_push_notifications": self.has_push_notifications,
            "has_state_transitions": self.has_state_transitions,
        }
        if self.provider_info:
            d["provider_info"] = self.provider_info
        if self.documentation_url:
            d["documentation_url"] = self.documentation_url
        return d
