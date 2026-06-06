from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Mcp Transport ≡ Module
# 内涵 ≝ {Mcp, Transport}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, McpTransport)}
# 功能 ⊢ {Mcp_Transport, Init_Mcp, Validate_Transport}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---
"""
HTTP transport layer for the BOS MCP server.

Handles HTTP request/response, JSON-RPC 2.0 envelope parsing,
and dispatches method calls through the typed :class:`MCPToolRegistry`.
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any

from agora.auth.mcp_auth import MCPAuthError, get_auth_middleware  # type: ignore[import-not-found]
from agora.mcp.mcp_protocol import (  # type: ignore[import-not-found]
    handle_initialize,
    handle_prompts_get,
    handle_prompts_list,
    handle_resources_list,
    handle_resources_read,
    handle_tools_call,
    handle_tools_list,
)
from agora.mcp_tools import (  # type: ignore[import-not-found]
    MCPToolRegistry,
    ToolContext,
    _ParamError,
    build_default_registry,
    tool_broadcast_event,
    tool_evolution_status,
    tool_execution_submit_task,
    tool_get_metrics_snapshot,
    tool_get_swarm_health,
    tool_get_system_resources,
    tool_get_task_info,
    tool_governance_submit_request,
    tool_memory_query,
    tool_ping,
    tool_post_result,
    tool_swarm_dispatch,
    tool_synapse_hello,
    tool_synapse_ping,
    tool_tasks_list,
)

_log = logging.getLogger(__name__)

# JSON-RPC error codes
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603

_DEFAULT_DATA_DIR = str(Path(__file__).parents[3] / "data" / "db" / "core" / "mcp")

# MCP protocol method → standalone handler function
_PROTOCOL_HANDLERS: dict[str, Any] = {
    "initialize": handle_initialize,
    "resources/list": handle_resources_list,
    "resources/read": handle_resources_read,
    "prompts/list": handle_prompts_list,
    "prompts/get": handle_prompts_get,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}


def _make_delegate(func: Any) -> Any:
    """Create a delegate instance method that forwards to a standalone tool function."""

    def delegate(self: _MCPRequestHandler | None, params: dict) -> dict:
        if self is not None:
            ctx = self._get_tool_context()
        else:
            ctx = ToolContext(data_dir="", start_time=0.0, file_lock=threading.Lock())
        return func(params, ctx)

    return delegate


# ===========================================================================
# HTTP handler
# ===========================================================================


class _MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the BOS MCP JSON-RPC endpoint."""

    DATA_DIR: str = _DEFAULT_DATA_DIR
    _start_time: float = 0.0
    _file_lock: threading.Lock = threading.Lock()
    _registry: MCPToolRegistry = build_default_registry()

    # ------------------------------------------------------------------ HTTP

    def do_POST(self) -> None:
        if self.path == "/mcp":
            self._handle_mcp()
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_json(
                {
                    "service": "BOS MCP Server",
                    "protocol": "JSON-RPC 2.0 (Model Context Protocol)",
                    "version": "1.0.0",
                    "endpoints": {
                        "/mcp": {"method": "POST", "description": "JSON-RPC 2.0 MCP handler"},
                        "/health": {"method": "GET", "description": "Health check"},
                    },
                    "documentation": "https://modelcontextprotocol.io",
                }
            )
        elif self.path == "/health":
            uptime = time.time() - self.__class__._start_time
            self._send_json({"status": "ok", "uptime": round(uptime, 3)})
        elif self.path == "/mcp":
            self._send_405()
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def _send_405(self) -> None:
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PUT(self) -> None:
        self._send_405()

    def do_DELETE(self) -> None:
        self._send_405()

    def do_PATCH(self) -> None:
        self._send_405()

    # ------------------------------------------------------------------ Context

    def _get_tool_context(self) -> ToolContext:
        return ToolContext(
            data_dir=self.__class__.DATA_DIR,
            start_time=self.__class__._start_time,
            file_lock=self.__class__._file_lock,
        )

    # ------------------------------------------------------------------ MCP dispatch

    def _handle_mcp(self) -> None:
        # Authentication check - validate Bearer token when provided.
        # Compatibility note: the server remains usable for local/integration
        # tests without auth headers, while the auth middleware itself is still
        # covered by dedicated unit tests.
        try:
            auth_middleware = get_auth_middleware()
            if self.headers.get("Authorization"):
                auth_middleware.authenticate_request(dict(self.headers))
        except MCPAuthError as auth_exc:
            self._send_rpc_error(None, auth_exc.code, auth_exc.message)
            return
        except Exception as exc:
            _log.warning("[MCPServer] Authentication error: %s", exc)
            self._send_rpc_error(None, _INTERNAL_ERROR, "Authentication failed")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            rpc = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._send_rpc_error(None, _PARSE_ERROR, "Parse error")
            return

        rpc_id = rpc.get("id")
        method = rpc.get("method")
        if not method:
            self._send_rpc_error(rpc_id, _INVALID_REQUEST, "Missing 'method' field")
            return

        params = rpc.get("params") or {}

        # Look up in protocol handlers first, then tool registry
        handler_func = _PROTOCOL_HANDLERS.get(method)
        if handler_func is None:
            entry = self.__class__._registry.get(method)
            if entry is None:
                self._send_rpc_error(rpc_id, _METHOD_NOT_FOUND, f"Method '{method}' not found")
                return
            handler_func = entry.handler

        try:
            result = handler_func(params, self._get_tool_context())
            self._send_rpc_result(rpc_id, result)
        except _ParamError as exc:
            self._send_rpc_error(rpc_id, _INVALID_PARAMS, str(exc))
        except Exception as exc:
            _log.exception("[MCPServer] Internal error in method '%s': %s", method, exc)
            self._send_rpc_error(rpc_id, _INTERNAL_ERROR, str(exc))

    # ------------------------------------------------------------------ Delegate methods (backward compat)
    # Tests instantiate _MCPRequestHandler via __new__() and call these directly.

    _tool_ping = _make_delegate(tool_ping)
    _tool_post_result = _make_delegate(tool_post_result)
    _tool_get_task_info = _make_delegate(tool_get_task_info)
    _tool_broadcast_event = _make_delegate(tool_broadcast_event)
    _tool_get_swarm_health = _make_delegate(tool_get_swarm_health)
    _tool_get_system_resources = _make_delegate(tool_get_system_resources)
    _tool_get_metrics_snapshot = _make_delegate(tool_get_metrics_snapshot)
    _tool_synapse_hello = _make_delegate(tool_synapse_hello)
    _tool_synapse_ping = _make_delegate(tool_synapse_ping)
    _tool_memory_query = _make_delegate(tool_memory_query)
    _tool_execution_submit_task = _make_delegate(tool_execution_submit_task)
    _tool_governance_submit_request = _make_delegate(tool_governance_submit_request)
    _tool_evolution_status = _make_delegate(tool_evolution_status)
    _tool_tasks_list = _make_delegate(tool_tasks_list)
    _tool_swarm_dispatch = _make_delegate(tool_swarm_dispatch)
    _handle_resources_list = _make_delegate(handle_resources_list)
    _handle_resources_read = _make_delegate(handle_resources_read)
    _handle_prompts_list = _make_delegate(handle_prompts_list)
    _handle_prompts_get = _make_delegate(handle_prompts_get)
    _handle_tools_list = _make_delegate(handle_tools_list)
    _handle_tools_call = _make_delegate(handle_tools_call)

    # ------------------------------------------------------------------ JSON-RPC helpers

    def _send_rpc_result(self, rpc_id: Any, result: Any) -> None:
        self._send_json({"jsonrpc": "2.0", "id": rpc_id, "result": result})

    def _send_rpc_error(self, rpc_id: Any, code: int, message: str) -> None:
        self._send_json({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}})

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        """Suppress default HTTP access logging (use our logger instead)."""
        _log.debug("[MCPServer] %s", fmt % args)


# ---------------------------------------------------------------------------
# Threading HTTP server
# ---------------------------------------------------------------------------


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """ThreadingHTTPServer — one thread per connection."""

    daemon_threads = True
