"""Agora MCP Proxy — unified downstream service aggregation.

Connects to multiple MCP services (stdio + HTTP), aggregates their
tool schemas, and exposes them through a single MCP entry point.

Supports dynamic load/unload (ref-count based), idle timeout for
automatic disconnection of inactive services, and lazy reconnection.
"""

from agora.mcp_proxy.client import (  # type: ignore[import-not-found]
    HttpMCPClient,
    MCPClient,
    StdioMCPClient,
    create_client,
)
from agora.mcp_proxy.idle_timeout import IdleTimeoutConfig, IdleTimeoutManager  # type: ignore[import-not-found]
from agora.mcp_proxy.manager import ProxyManager  # type: ignore[import-not-found]
from agora.mcp_proxy.registry import ProxyEntry, ProxyRegistry  # type: ignore[import-not-found]

__all__ = [
    "MCPClient",
    "StdioMCPClient",
    "HttpMCPClient",
    "create_client",
    "ProxyRegistry",
    "ProxyEntry",
    "ProxyManager",
    "IdleTimeoutConfig",
    "IdleTimeoutManager",
]
