"""agora.server.mcp_entry — HTTP / SSE transport entry points (P110 split).

P110 关联: TASK-F7114ABA (omo lint god-module 800L 硬规则).
agora/server/mcp.py 806L 拆分: http_main / sse_main (~180L) 独立到本模块,
agora/server/mcp.py 降至 <800L. main() 仍保留在 mcp.py (CLI 入口),
http_main / sse_main 在 mcp.py 顶层 re-export 保持调用方不变.

模式: agora/server/mcp.py 用 `from .mcp_entry import http_main, sse_main`
顶层 re-export, 已有调用方 `from agora.server.mcp import http_main` 不破.

统一路由: /v1/tools/call 与 /v1/backends/register 曾仅 HTTP 模式注册,
SSE 模式 (7431) 无 → bos mutate 连 7431 404。现抽 `_register_common_routes`
供 http_main / sse_main 共用, 两模式均暴露 /health + /v1/tools/call +
/v1/backends/register (+ SSE 额外 a2a)。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from agora.server.mcp import logger, mcp


def _register_common_routes() -> None:
    """Register /health + /v1/tools/call + /v1/backends/register on the shared MCP app.

    HTTP 与 SSE 模式共用: 保证 bos mutate (tools/call) 与动态后端注册在两种
    传输下均可用。SSE 模式额外注册 a2a 路由 (在 sse_main 中追加)。
    """

    async def health_endpoint(request):
        from agora.server.tools_health import health_self_check

        try:
            result = await health_self_check()
            return JSONResponse(result)
        except Exception:  # defensive fallback
            return JSONResponse(
                {
                    "status": "ok",
                    "service": "agora-mcp",
                    "tools": len(await mcp.list_tools()),
                }
            )

    async def tool_call_endpoint(request: Request):
        from agora.server.request_context import reset_http_request, set_http_request

        # FastMCP dependency injection looks at the HTTP request to find the request.
        # P2-6: 统一经 request_context 注入, 不直接依赖 fastmcp 私有 API。
        token = set_http_request(request)
        try:
            payload = await request.json()
            tool_name = payload.get("name")
            arguments = payload.get("arguments", {})
            if not tool_name:
                return JSONResponse({"error": "Missing tool name"}, status_code=400)
            # AGORA_API_KEY present in env → FastMCP AuthMiddleware validates
            # the Authorization header from the request we just set.
            result = await mcp.call_tool(tool_name, arguments)
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
            reset_http_request(token)

    async def register_backend_endpoint(request: Request):
        """POST /v1/backends/register — dynamically register a new MCP backend.

        P0-SEC: 高风险端点 (接受任意 command/args 并 spawn 子进程)。
        复用 require_agora_api_key 校验 Bearer token; AGORA_AUTH_MODE=permissive
        时本地开发放行。拒绝未认证调用 (401)。
        """
        from agora.mcp_proxy.manager import ProxyManager
        from agora.server.dependencies import get_proxy_manager, set_proxy_manager
        from agora.server.request_context import reset_http_request, set_http_request
        from agora.server.tools_auth import require_agora_api_key

        # 注入 HTTP 上下文供鉴权中间件读取 (与 tool_call_endpoint 一致)
        token = set_http_request(request)
        try:
            # 校验认证: permissive 放行; required+有 key 需 Bearer token 匹配
            from fastmcp.server.auth.authorization import AuthContext

            auth_ctx = AuthContext(token=None, component=None)
            if not require_agora_api_key(auth_ctx):
                return JSONResponse({"error": "unauthorized"}, status_code=401)

            try:
                payload = await request.json()
            except Exception:  # defensive fallback
                return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
            name = payload.get("name", "")
            if not name:
                return JSONResponse({"error": "Missing 'name' field"}, status_code=400)
            # P0-SEC: 拒绝明显危险的 command (shell 注入向量)
            command = payload.get("command", "")
            if isinstance(command, str) and any(
                tok in command for tok in (";", "|", "&&", "`", "$(")
            ):
                return JSONResponse(
                    {"error": "command contains shell metacharacters"},
                    status_code=400,
                )
            pm = get_proxy_manager()
            if pm is None:
                pm = ProxyManager()
                set_proxy_manager(pm)
            svc: dict = {"name": name}
            if command:
                svc["command"] = command
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
        finally:
            reset_http_request(token)

    async def metrics_endpoint(request: Request):
        """GET /metrics — Prometheus scrape endpoint.

        P2-1: 暴露进程内指标 (prometheus_client), 供外部 Prometheus/Grafana 接入。
        与 /health 一致, 不走 AuthMiddleware (仅暴露聚合指标, 无敏感数据)。
        """
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
        except Exception:  # defensive fallback
            logger.exception("metrics_scrape_failed")
            return JSONResponse({"error": "metrics_unavailable"}, status_code=500)

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
    mcp._additional_http_routes.append(Route("/metrics", endpoint=metrics_endpoint))


def http_main() -> None:
    """Start the Agora MCP server in HTTP mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    """
    _register_common_routes()
    asyncio.run(
        mcp.run_http_async(
            host="0.0.0.0", port=int(os.environ.get("AGORA_MCP_HTTP_PORT", "7422"))
        )
    )


def sse_main() -> None:
    """Start the Agora MCP server in SSE mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    Exposes /health + /v1/tools/call + /v1/backends/register alongside SSE
    transport (共用 _register_common_routes), plus a2a.
    """
    from agora.server.a2a import a2a_send_endpoint

    _register_common_routes()
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
