"""Base data classes and helpers for the service registry."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from urllib.parse import urlparse

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
]

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "metadata.google.internal",
        "169.254.169.254",
    }
)

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


def _is_private_ip(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_NETWORKS)


def validate_external_url(url: str) -> None:
    """Validate URL points to external address. Raises ValueError if not."""
    if not url:
        raise ValueError("URL不能为空")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的协议: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise ValueError(f"无法解析主机: {url}")
    if host.lower() in _BLOCKED_HOSTS:
        raise ValueError(f"禁止访问保留主机: {host}")
    if host.lower().endswith((".local", ".internal")):
        raise ValueError(f"禁止访问内部主机: {host}")
    if _is_private_ip(host):
        raise ValueError(f"禁止访问内网地址: {host}")


def is_safe_url(url: str) -> bool:
    """Validate URL does not target internal/private network resources."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        validate_external_url(url)
        return True
    except ValueError:
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
