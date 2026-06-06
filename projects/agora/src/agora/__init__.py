"""Agora — MCP Service Convergence Hub.

Routes, monitors, and governs communication between MCP-based services.
Single-registry hub-spoke topology: every service knows only Agora; Agora
knows every service.
"""

__version__ = "2.0.0"

# ── D-Gateway extracted modules (zero/low coupling) ──────────────────────────
# These were migrated from SharedBrain/organs/D_Gateway/ and are self-contained
# with no nucleus dependencies.  See each module's docstring for details.

from . import (
    api_types,  # type: ignore[import-not-found]
    connection_pool,  # type: ignore[import-not-found]
    umbilical_protocol,  # type: ignore[import-not-found]
    unified_protocol_adapter,  # type: ignore[import-not-found]
)
from .auth import (
    auth_models,  # type: ignore[import-not-found]
)
from .mcp import (
    base_tool,  # type: ignore[import-not-found]
    tool_contract,  # type: ignore[import-not-found]
    tools_template,  # type: ignore[import-not-found]
)

__all__ = (
    "api_types",
    "auth_models",
    "base_tool",
    "connection_pool",
    "tool_contract",
    "tools_template",
    "umbilical_protocol",
    "unified_protocol_adapter",
)

"""
Agora — MCP 服务融合 Hub。

跨项目桥接:
- agora → sophia: 共享 MCP 生态，paradigm 编译可复用
- agora → minerva: 共享 fastmcp 基础设施
- agora → pallas: pallas 通过 subprocess 调用 agora CLI
"""
