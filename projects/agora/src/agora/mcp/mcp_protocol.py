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
# Mcp Protocol ≡ Module
# 内涵 ≝ {Mcp, Protocol}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, McpProtocol)}
# 功能 ⊢ {Mcp_Protocol, Init_Mcp, Validate_Protocol}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---
"""
MCP resource, prompt, and tool-discovery protocol handlers.

Implements the ``resources/*``, ``prompts/*``, and ``tools/*`` endpoints,
plus the required MCP ``initialize`` handshake (2024-11-05).
"""

import asyncio
import logging
from typing import Any  # noqa: F401

from agora.mcp_tools import ToolContext, _ParamError  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)
_SUPPORTED_PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------------------
# MCP initialize (RFC 2024-11-05)
# ---------------------------------------------------------------------------


def handle_initialize(params: dict, ctx: ToolContext) -> dict:
    """MCP initialize — required handshake per MCP protocol 2024-11-05."""
    return {
        "protocolVersion": _SUPPORTED_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {},
            "resources": {},
            "prompts": {},
        },
        "serverInfo": {
            "name": "BOS MCP Server",
            "version": "1.0.0",
        },
    }


_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP resources (MCP-01)
# ---------------------------------------------------------------------------


def handle_resources_list(params: dict, ctx: ToolContext) -> dict:
    """MCP resources/list — enumerate available B-OS resources."""
    return {
        "resources": [
            {
                "uri": "bos://memory/docs/readme",
                "name": "B-OS README",
                "description": "Project overview and quick start",
                "mimeType": "text/markdown",
            },
            {
                "uri": "bos://execution/workers/status",
                "name": "Worker Pool Status",
                "description": "Current worker pool metrics",
                "mimeType": "application/json",
            },
            {
                "uri": "bos://governance/roles/list",
                "name": "Role Definitions",
                "description": "Available B-OS roles",
                "mimeType": "application/json",
            },
        ]
    }


def handle_resources_read(params: dict, ctx: ToolContext) -> dict:
    """MCP resources/read — fetch a specific resource by URI."""
    uri = params.get("uri", "")
    
    if uri.startswith("bos://memory/"):
        path = uri[len("bos://memory/"):]
        try:
            from ecos.mcp_vfs import read_memory_resource
            content = read_memory_resource(path)
            return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": content}]}
        except ImportError:
            return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"Error: ecos mcp_vfs not found for {uri}"}]}
            
    elif uri.startswith("bos://omo/"):
        path = uri[len("bos://omo/"):]
        try:
            from ecos.mcp_vfs import read_omo_resource
            content = read_omo_resource(path)
            return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": content}]}
        except ImportError:
            return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"Error: ecos mcp_vfs not found for {uri}"}]}
            
    if uri == "bos://execution/workers/status":
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": '{"status": "ok"}'}]}
    else:
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"Resource not found: {uri}"}]}


# ---------------------------------------------------------------------------
# MCP prompts (MCP-01)
# ---------------------------------------------------------------------------


def handle_prompts_list(params: dict, ctx: ToolContext) -> dict:
    """MCP prompts/list — enumerate available prompt templates."""
    return {
        "prompts": [
            {
                "name": "analyze_code",
                "description": "Analyze a code snippet for quality and correctness",
                "arguments": [
                    {"name": "code", "description": "The code to analyze", "required": True},
                    {
                        "name": "language",
                        "description": "Programming language",
                        "required": False,
                    },
                ],
            },
            {
                "name": "debug_error",
                "description": "Help debug an error with context",
                "arguments": [
                    {
                        "name": "error",
                        "description": "Error message or traceback",
                        "required": True,
                    },
                    {
                        "name": "context",
                        "description": "Additional context",
                        "required": False,
                    },
                ],
            },
            {
                "name": "bos_query",
                "description": "Query the B-OS system via natural language",
                "arguments": [
                    {
                        "name": "query",
                        "description": "Natural language query",
                        "required": True,
                    },
                ],
            },
        ]
    }


def handle_prompts_get(params: dict, ctx: ToolContext) -> dict:
    """MCP prompts/get — get a specific prompt template with filled arguments."""
    name = params.get("name", "")
    arguments = params.get("arguments", {})

    templates = {
        "analyze_code": (
            "Please analyze the following {language} code:\n\n"
            "```{language}\n{code}\n```\n\n"
            "Provide quality assessment, potential bugs, and improvements."
        ),
        "debug_error": "Help me debug this error:\n\n{error}\n\nContext: {context}",
        "bos_query": "Query the B-OS system: {query}",
    }

    if name not in templates:
        return {"error": {"code": -32602, "message": f"Prompt '{name}' not found"}}

    template = templates[name]
    filled = template.format(**{k: arguments.get(k, f"{{{k}}}") for k in arguments})

    return {
        "description": f"Prompt: {name}",
        "messages": [{"role": "user", "content": {"type": "text", "text": filled}}],
    }


# ---------------------------------------------------------------------------
# MCP tool discovery & invocation (MCP-02)
# ---------------------------------------------------------------------------


def handle_tools_list(params: dict, ctx: ToolContext) -> dict:
    """MCP tools/list — enumerate all tools registered in the ToolRegistry."""
    tools: list[dict] = []
    try:
        get_default_registry = __import__(
            "organs.D_Execution.organs.tool_registry",
            fromlist=["get_default_registry"],
        ).get_default_registry
        registry = get_default_registry()
        tools = registry.to_anthropic_tools()
    except (ImportError, KeyError, AttributeError) as exc:
        _log.warning("[MCPServer] tools/list: D-Execution registry unavailable — %s", exc)

    if not tools:
        tools = _get_builtin_mcp_tools()
    return {"tools": tools}


def _get_builtin_mcp_tools() -> list[dict]:
    """Return built-in MCP tools when D-Execution registry is unavailable."""
    return [
        {
            "name": "bos_ping",
            "description": "Ping the B-OS MCP server to verify connectivity",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "bos_health",
            "description": "Get basic B-OS daemon health information",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


def handle_tools_call(params: dict, ctx: ToolContext) -> dict:
    """MCP tools/call — invoke a registered tool by name with given arguments."""
    tool_name = params.get("name")
    arguments = params.get("arguments") or {}
    if not tool_name:
        raise _ParamError("Missing required param: 'name'")

    # Built-in tool handlers (when D-Execution registry unavailable)
    builtin_result = _handle_builtin_tool(tool_name, arguments)
    if builtin_result is not None:
        return builtin_result

    try:
        get_default_registry = __import__(
            "organs.D_Execution.organs.tool_registry",
            fromlist=["get_default_registry"],
        ).get_default_registry
        registry = get_default_registry()

        loop = asyncio.new_event_loop()
        try:
            tool_result = loop.run_until_complete(registry.invoke_async(tool_name, arguments))
        finally:
            loop.close()

        if tool_result.is_error:
            error_msg = getattr(tool_result, "error_message", str(tool_result.content))
            return {
                "content": [{"type": "text", "text": f"[tool error] {error_msg}"}],
                "isError": True,
            }
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(tool_result.content) if tool_result.content is not None else "",
                }
            ]
        }
    except _ParamError:
        raise
    except (ImportError, KeyError, AttributeError) as exc:
        _log.error("[MCPServer] tools/call '%s' failed: %s", tool_name, exc)
        return {
            "content": [{"type": "text", "text": f"[internal error] {exc}"}],
            "isError": True,
        }


def _handle_builtin_tool(tool_name: str, arguments: dict) -> dict | None:
    """Handle built-in MCP tools. Returns result dict or None if not a built-in tool."""
    import json
    import time

    if tool_name == "bos_ping":
        return {
            "content": [{"type": "text", "text": "pong"}],
        }
    if tool_name == "bos_health":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "healthy",
                            "service": "BOS MCP Server",
                            "version": "1.0.0",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        },
                        indent=2,
                    ),
                }
            ],
        }
    return None
