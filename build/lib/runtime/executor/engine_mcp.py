"""Engine MCP — Model Context Protocol handler for agent-runtime.

Manages MCP tool registration, discovery, and invocation within the
engine layer. Complements the existing mcp_server.py (which exposes
agent-runtime as an MCP server).

"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from runtime.executor.engine_types import EngineError, ErrorCategory, ErrorSeverity

# ====================================================================
# MCP Types
# ====================================================================

ToolHandler = Callable[..., Awaitable[str]]


@dataclass
class MCPTool:
    """An MCP tool registration."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    handler: ToolHandler | None = None


@dataclass
class MCPCallRequest:
    """Incoming MCP tool call."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""


@dataclass
class MCPCallResult:
    """Result of an MCP tool call."""

    success: bool = True
    content: str = ""
    error: str | None = None
    request_id: str = ""


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""

    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


# ====================================================================
# MCP Protocol Error
# ====================================================================


class MCPError(EngineError):
    """MCP-specific error."""

    def __init__(self, message: str, tool: str = "", **kw: Any) -> None:
        super().__init__(message, ErrorCategory.PLUGIN, ErrorSeverity.RECOVERABLE, False, {"tool": tool, **kw})


# ====================================================================
# MCP Handler — Tool Registry & Dispatch
# ====================================================================


class MCPHandler:
    """Registry and dispatcher for MCP tools.

    Manages tool registration, discovery, and invocation.
    """

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}
        self._servers: dict[str, MCPServerConfig] = {}

    def register_tool(self, tool: MCPTool) -> None:
        """Register an MCP tool with its handler."""
        if tool.name in self._tools:
            raise MCPError(f"Tool already registered: {tool.name}", tool=tool.name)
        self._tools[tool.name] = tool

    def unregister_tool(self, name: str) -> bool:
        """Remove a tool registration."""
        return self._tools.pop(name, None) is not None

    def get_tool(self, name: str) -> MCPTool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools as JSON-compatible dicts."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def call_tool(self, request: MCPCallRequest) -> MCPCallResult:
        """Call a registered MCP tool by name."""
        tool = self._tools.get(request.tool)
        if tool is None:
            return MCPCallResult(
                success=False,
                error=f"Tool not found: {request.tool}",
                request_id=request.request_id,
            )
        if tool.handler is None:
            return MCPCallResult(
                success=False,
                error=f"Tool {request.tool} has no handler registered",
                request_id=request.request_id,
            )
        try:
            content = await tool.handler(**request.arguments)
            return MCPCallResult(success=True, content=str(content), request_id=request.request_id)
        except Exception as e:
            return MCPCallResult(
                success=False,
                error=f"Tool {request.tool} failed: {e}",
                request_id=request.request_id,
            )

    def register_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server configuration."""
        self._servers[config.name] = config

    def list_servers(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def get_server(self, name: str) -> MCPServerConfig | None:
        return self._servers.get(name)

    def build_tool_schemas(self) -> list[dict[str, Any]]:
        """Build MCP tool schemas for LLM function calling."""
        schemas: list[dict[str, Any]] = []
        for tool in self._tools.values():
            schema: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            }
            if tool.parameters:
                schema["input_schema"]["properties"] = {
                    k: {"type": v.get("type", "string"), "description": v.get("description", "")}
                    for k, v in tool.parameters.items()
                }
            schemas.append(schema)
        return schemas
