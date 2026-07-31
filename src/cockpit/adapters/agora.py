"""Anti-corruption adapter for projects/agora (I0).

Re-exports the agora BOS / MCP / proxy symbols used by cockpit commands and
dashboard API routes.
"""

from agora.auth.mcp_gateway import KNOWN_BACKENDS, _health_checker
from agora.core.service_base import Service
from agora.core.state import get_registry
from agora.mcp.bos_metrics import bos_metrics
from agora.mcp.bos_middleware import bos_cache
from agora.mcp.resolver.api import parse_bos_uri, resolve_bos_uri
from agora.mcp.resolver.bos_registry import DEFAULT_REGISTRY_PATH, load_from_yaml
from agora.mcp.resolver.services import POC_SERVICES
from agora.mcp.swarm import get_swarm
from agora.mcp_proxy.manager import ProxyManager
from agora.server.dependencies import get_proxy_manager, set_proxy_manager
from agora.server.tools_proxy import register_proxy_tools

__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "KNOWN_BACKENDS",
    "POC_SERVICES",
    "ProxyManager",
    "Service",
    "_health_checker",
    "bos_cache",
    "bos_metrics",
    "get_proxy_manager",
    "get_registry",
    "get_swarm",
    "load_from_yaml",
    "parse_bos_uri",
    "register_proxy_tools",
    "resolve_bos_uri",
    "set_proxy_manager",
]
