from __future__ import annotations

"""
---
Type: Organ
Layer: L3
Domain: D-Gateway
Status: ACTIVE
Version: 1.0.0
Summary: MCP (Model Context Protocol) handler implementation
Authority: D-Gateway/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Mcp Protocol Handler ≡ Handler
# 内涵 ≝ {Mcp, Protocol, Handler}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, McpProtocolHandler)}
# 功能 ⊢ {Mcp_Protocol, Protocol_Handler, Handler_Init}
# =============================================================================


import json  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402
from collections.abc import Callable  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import Any  # noqa: E402

from agora.unified_protocol_adapter import ProtocolVersion  # type: ignore[import-not-found]  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class MCPRequest:
    """MCP protocol request structure."""

    jsonrpc: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: int | str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPRequest:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            method=data.get("method", ""),
            params=data.get("params", {}),
            id=data.get("id"),
        )


@dataclass
class MCPResponse:
    """MCP protocol response structure."""

    jsonrpc: str = "2.0"
    result: Any = None
    error: dict[str, Any] | None = None
    id: int | str | None = None

    def to_dict(self) -> dict[str, Any]:
        response: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response


class MCPProtocolHandler:
    """MCP protocol handler with full spec compliance.

    Features:
    1. JSON-RPC 2.0 compliance
    2. Batch request support
    3. Method registry with versioning
    4. Error handling per spec
    """

    SUPPORTED_VERSION = ProtocolVersion(2, 0, 0)

    # JSON-RPC 2.0 error codes
    ERROR_PARSE_ERROR = -32700
    ERROR_INVALID_REQUEST = -32600
    ERROR_METHOD_NOT_FOUND = -32601
    ERROR_INVALID_PARAMS = -32602
    ERROR_INTERNAL_ERROR = -32603
    ERROR_SERVER_ERROR = -32000

    def __init__(self) -> None:
        self._methods: dict[str, tuple[Callable, ProtocolVersion]] = {}
        self._middleware: list[Callable] = []

    def register_method(
        self, name: str, handler: Callable, version: ProtocolVersion | None = None
    ) -> None:
        """Register an MCP method handler."""
        self._methods[name] = (handler, version or self.SUPPORTED_VERSION)
        logger.info(
            "[MCP] Registered method: %s (v%s)", name, version or self.SUPPORTED_VERSION
        )

    def add_middleware(self, middleware: Callable) -> None:
        """Add request middleware."""
        self._middleware.append(middleware)

    async def handle(
        self, request_data: dict[str, Any] | list[Any]
    ) -> dict[str, Any] | list[Any] | None:
        """Handle MCP request(s).

        Supports single requests and batch requests.
        """
        # Batch request
        if isinstance(request_data, list):
            if not request_data:
                return self._error_response(
                    None, self.ERROR_INVALID_REQUEST, "Invalid batch"
                )

            responses = []
            for req in request_data:
                response = await self._handle_single(req)
                if response:  # Skip notifications (no id)
                    responses.append(response)
            return responses if responses else None

        # Single request
        return await self._handle_single(request_data)

    async def _handle_single(
        self, request_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Handle a single MCP request."""
        # Parse request
        try:
            request = MCPRequest.from_dict(request_data)
        except (KeyError, ValueError, TypeError) as e:
            return self._error_response(None, self.ERROR_PARSE_ERROR, str(e))
        if request.jsonrpc != "2.0":
            return self._error_response(
                request.id, self.ERROR_INVALID_REQUEST, "Invalid JSON-RPC version"
            )

        # Run middleware
        context = {"request": request, "timestamp": time.time()}
        for middleware in self._middleware:
            try:
                import inspect

                if inspect.iscoroutinefunction(middleware):
                    context = await middleware(context)
                else:
                    context = middleware(context)
            except (OSError, ValueError, RuntimeError, KeyError) as e:
                logger.error("[MCP] Middleware error: %s", str(e))
                return self._error_response(
                    request.id, self.ERROR_INTERNAL_ERROR, str(e)
                )

        # Find method
        if request.method not in self._methods:
            return self._error_response(
                request.id,
                self.ERROR_METHOD_NOT_FOUND,
                f"Method not found: {request.method}",
            )

        handler, version = self._methods[request.method]

        # Execute handler
        try:
            import inspect

            if inspect.iscoroutinefunction(handler):
                result = await handler(request.params, context)
            else:
                result = handler(request.params, context)

            # Notification (no id) - no response
            if request.id is None:
                return None

            return self._success_response(request.id, result)

        except TypeError as e:
            return self._error_response(request.id, self.ERROR_INVALID_PARAMS, str(e))
        except (OSError, ValueError, RuntimeError, KeyError) as e:
            logger.error("[MCP] Handler error for %s: %s", request.method, str(e))
            return self._error_response(request.id, self.ERROR_INTERNAL_ERROR, str(e))

    def _success_response(
        self, req_id: int | str | None, result: Any
    ) -> dict[str, Any]:
        """Build success response."""
        return MCPResponse(id=req_id, result=result).to_dict()

    def _error_response(
        self, req_id: int | str | None, code: int, message: str, data: Any = None
    ) -> dict[str, Any]:
        """Build error response."""
        error = {"code": code, "message": message}
        if data:
            error["data"] = data
        return MCPResponse(id=req_id, error=error).to_dict()

    def get_capabilities(self) -> dict[str, Any]:
        """Get MCP server capabilities."""
        return {
            "protocolVersion": str(self.SUPPORTED_VERSION),
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "prompts": {"listChanged": True},
                "logging": {},
                "experimental": {},
            },
            "serverInfo": {"name": "B-OS-MCP-Server", "version": "10.0.0"},
            "methods": list(self._methods.keys()),
        }


class MCPResourceManager:
    """MCP resources management."""

    def __init__(self) -> None:
        self._resources: dict[str, dict[str, Any]] = {}
        self._templates: dict[str, Callable] = {}

    def register_resource(self, uri: str, resource: dict[str, Any]) -> None:
        """Register a static resource."""
        self._resources[uri] = resource
        logger.info("[MCP] Registered resource: %s", uri)

    def register_template(self, uri_template: str, handler: Callable) -> None:
        """Register a resource template handler."""
        self._templates[uri_template] = handler
        logger.info("[MCP] Registered template: %s", uri_template)

    def get_resource(self, uri: str) -> dict[str, Any] | None:
        """Get resource by URI."""
        # Check static resources
        if uri in self._resources:
            return self._resources[uri]

        # Check templates
        for template, handler in self._templates.items():
            # Simple template matching
            if self._match_template(template, uri):
                try:
                    result = handler(uri)
                    return result
                except (OSError, ValueError, RuntimeError, KeyError) as e:
                    logger.error("[MCP] Template handler error: %s", str(e))

        return None

    def _match_template(self, template: str, uri: str) -> bool:
        """Simple template matching."""
        # Convert template pattern to simple matching
        import re

        pattern = template.replace("{", "(?P<").replace("}", ">[^/]+)")
        return bool(re.match(f"^{pattern}$", uri))

    def list_resources(self) -> list[dict[str, Any]]:
        """List all registered resources."""
        resources = []
        for uri, resource in self._resources.items():
            resources.append(
                {
                    "uri": uri,
                    "name": resource.get("name", uri),
                    "mimeType": resource.get("mimeType", "application/json"),
                    **{
                        k: v
                        for k, v in resource.items()
                        if k not in ["name", "mimeType", "content"]
                    },
                }
            )
        return resources


class MCPToolManager:
    """MCP tools management."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable] = {}

    def register_tool(
        self, name: str, schema: dict[str, Any], handler: Callable
    ) -> None:
        """Register an MCP tool."""
        self._tools[name] = {
            "name": name,
            "description": schema.get("description", ""),
            "inputSchema": schema.get("inputSchema", {"type": "object"}),
        }
        self._handlers[name] = handler
        logger.info("[MCP] Registered tool: %s", name)

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Call an MCP tool."""
        if name not in self._handlers:
            raise ValueError(f"Tool not found: {name}")

        handler = self._handlers[name]
        import inspect

        if inspect.iscoroutinefunction(handler):
            result = await handler(arguments)
        else:
            result = handler(arguments)

        return self._format_result(result)

    def _format_result(self, result: Any) -> list[dict[str, Any]]:
        """Format tool result to MCP content format."""
        if isinstance(result, list):
            return result

        if isinstance(result, str):
            return [{"type": "text", "text": result}]

        return [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        return list(self._tools.values())
