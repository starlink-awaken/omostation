"""Agora — MCP Service Convergence Hub.

Routes, monitors, and governs communication between MCP-based services.
Single-registry hub-spoke topology: every service knows only Agora; Agora
knows every service.
"""

__version__ = "3.0.0"

from .auth import (
    auth_models,
)
from .mcp import (
    base_tool,
    tool_contract,
    tools_template,
)

__all__ = (
    "auth_models",
    "base_tool",
    "tool_contract",
    "tools_template",
)
