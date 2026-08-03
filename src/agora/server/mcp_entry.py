"""agora.server.mcp_entry — HTTP / SSE transport entry points (P110 split).

P110 关联: TASK-F7114ABA (omo lint god-module 800L 硬规则).
agora/server/mcp.py 806L 拆分: http_main / sse_main (~180L) 独立到本模块,
agora/server/mcp.py 降至 <800L. main() 仍保留在 mcp.py (CLI 入口),
http_main / sse_main 在 mcp.py 顶层 re-export 保持调用方不变.

模式: agora/server/mcp.py 用 `from .mcp_entry import http_main, sse_main`
顶层 re-export, 已有调用方 `from agora.server.mcp import http_main` 不破.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from agora.server.mcp import logger, mcp

__all__ = ["http_main", "sse_main"]


def http_main() -> None:
    """Start the Agora MCP server in HTTP mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health_endpoint(request):
        from agora.server.tools_health import health_self_check

        try:
            result = await health_self_check()
            return JSONResponse(result)
        except Exception:  # defensive fallback
            return JSONResponse(
                {
                    "status": "ok",
                    "service": "agora-mcp-http",
                    "tools": len(await mcp.list_tools()),
                }
            )

    async def tool_call_endpoint(request: Request):
        from fastmcp.server.dependencies import _current_http_request

        # FastMCP dependency injection looks at _current_http_request to find the HTTP request
        token = _current_http_request.set(request)
        try:
            payload = await request.json()
            tool_name = payload.get("name")
            arguments = payload.get("arguments", {})
            if not tool_name:
                return JSONResponse({"error": "Missing tool name"}, status_code=400)
            # If AGORA_API_KEY is present in env, FastMCP's AuthMiddleware will look for it
            # It will extract it from the Authorization header of the request object we just set.
            result = await mcp.call_tool(tool_name, arguments)
            # FastMCP call_tool returns a CallToolResult object or string
            res_content = ""
            if (
                hasattr(result, "content")
                and isinstance(result.content, list)
                and result.content
            ):
                res_content = getattr(result.content[0], "text", str(result.content[0]))
            elif isinstance(result, list) and result:
                res_content = getattr(result[0], "text", str(result[0]))
            else:
                res_content = str(result)
            try:
                parsed_res = json.loads(res_content)
            except (json.JSONDecodeError, TypeError):
                parsed_res = res_content
            return JSONResponse({"status": "ok", "result": parsed_res})
        except Exception:  # defensive fallback
            logger.exception("REST tool call failed")
            return JSONResponse({"error": "internal"}, status_code=500)
        finally:
            _current_http_request.reset(token)

    async def register_backend_endpoint(request: Request):
        """POST /v1/backends/register — dynamically register a new MCP backend."""
        from agora.mcp_proxy.manager import ProxyManager
        from agora.server.dependencies import get_proxy_manager, set_proxy_manager

        try:
            payload = await request.json()
        except Exception:  # defensive fallback
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        name = payload.get("name", "")
        if not name:
            return JSONResponse({"error": "Missing 'name' field"}, status_code=400)
        pm = get_proxy_manager()
        if pm is None:
            pm = ProxyManager()
            set_proxy_manager(pm)
        svc: dict = {"name": name}
        if payload.get("command"):
            svc["command"] = payload["command"]
        if payload.get("args"):
            svc["args"] = payload["args"]
        if payload.get("mcp_endpoint"):
            svc["mcp_endpoint"] = payload["mcp_endpoint"]
        try:
            result = await pm.add_service(svc)
            logger.info("backend_registered_via_api", name=name, result=result)
            return JSONResponse({"status": "ok", "name": name, "result": result})
        except Exception:  # defensive fallback
            logger.exception("backend_register_failed", name=name)
            return JSONResponse({"error": "internal"}, status_code=500)

    mcp._additional_http_routes.append(Route("/health", endpoint=health_endpoint))
    mcp._additional_http_routes.append(
        Route("/v1/tools/call", endpoint=tool_call_endpoint, methods=["POST"])
    )
    mcp._additional_http_routes.append(
        Route(
            "/v1/backends/register",
            endpoint=register_backend_endpoint,
            methods=["POST"],
        )
    )

    asyncio.run(
        mcp.run_http_async(
            host="0.0.0.0", port=int(os.environ.get("AGORA_MCP_HTTP_PORT", "7422"))
        )
    )


def sse_main() -> None:
    """Start the Agora MCP server in SSE mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    Exposes a /health HTTP endpoint alongside the SSE transport.
    """
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health_endpoint(request):
        from agora.server.tools_health import health_self_check

        try:
            result = await health_self_check()
            return JSONResponse(result)
        except Exception:  # defensive fallback
            return JSONResponse(
                {
                    "status": "ok",
                    "service": "agora-mcp-sse",
                    "tools": len(await mcp.list_tools()),
                }
            )

    from agora.server.a2a import a2a_send_endpoint

    mcp._additional_http_routes.append(Route("/health", endpoint=health_endpoint))
    mcp._additional_http_routes.append(
        Route("/api/v1/a2a/send", endpoint=a2a_send_endpoint, methods=["POST"])
    )
    sys.stderr.write("Agora MCP Server (SSE) starting on port 7431...\n")
    asyncio.run(
        mcp.run_http_async(
            transport="sse",
            host="0.0.0.0",
            port=int(os.environ.get("AGORA_MCP_SSE_PORT", "7431")),
        )
    )
