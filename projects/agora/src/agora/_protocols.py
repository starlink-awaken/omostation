"""Protocol handlers — extracted from Router for module size compliance.

Each handler is a standalone async function that takes the tool name, arguments,
and instance dict. The dispatch function routes to the appropriate handler.
"""

from __future__ import annotations

import asyncio
import importlib
import json as _json

import httpx
import structlog
from httpx import Limits

from agora.core.service_base import is_safe_url  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)


def _check_ssrf(url: str, tool_name: str = "") -> dict | None:
    """Check URL for SSRF. Returns error dict if blocked, None if safe."""
    if url.startswith("http") and not is_safe_url(url):
        if tool_name:
            logger.warning("ssrf_blocked", tool=tool_name, url=url)
        return {"status": "error", "error": "Service unavailable"}
    return None


# ── Connection pool singleton ──────────────────────────────────────

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return the shared httpx AsyncClient singleton."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30, limits=Limits(max_keepalive_connections=20))
    return _client


async def close_client():
    """Clean up the shared HTTP client connection pool."""
    global _client
    if _client:
        await _client.aclose()
        _client = None


# ── Protocol dispatch ───────────────────────────────────────────────


async def dispatch(instance: dict, tool_name: str, arguments: dict) -> dict:
    """Route a tool call to the correct protocol handler."""
    protocol = instance.get("protocol", "mcp")

    if protocol == "mcp":
        return await _call_mcp(tool_name, arguments, instance["mcp_endpoint"])
    elif protocol == "rest":
        return await _call_rest(tool_name, arguments, instance)
    elif protocol == "grpc":
        return await _call_grpc(tool_name, arguments, instance)
    elif protocol == "websocket":
        return await _call_ws(tool_name, arguments, instance)
    elif protocol == "stdio":
        return {"status": "error", "error": "stdio protocol uses proxy, not router"}
    else:
        return {"status": "error", "error": f"Unknown protocol: {protocol}"}


# ── MCP handler ─────────────────────────────────────────────────────


async def _call_mcp(tool_name: str, arguments: dict, mcp_endpoint: str, trace_ctx: dict | None = None) -> dict:
    """Execute an MCP tools/call request against the target endpoint.

    Args:
        tool_name: Tool name to call
        arguments: Tool arguments
        mcp_endpoint: MCP endpoint URL
        trace_ctx: Optional trace context (新增：支持跨语言追踪)
    """
    if err := _check_ssrf(mcp_endpoint, tool_name):
        return err

    # 构建请求，带 trace context
    payload: dict = {"method": "tools/call", "params": {"name": tool_name, "arguments": arguments}}

    # 新增：注入 trace context 到请求
    if trace_ctx:
        payload["_trace"] = {
            "trace_id": trace_ctx.get("trace_id", ""),
            "parent_id": trace_ctx.get("parent_id", ""),
            "service": trace_ctx.get("service", "agora"),
            "phase": trace_ctx.get("phase", ""),
        }

    client = _get_client()
    resp = await client.post(
        mcp_endpoint,
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


# ── REST handler ────────────────────────────────────────────────────


async def _call_rest(tool_name: str, arguments: dict, instance: dict) -> dict:
    """Execute a REST API call against the target endpoint.

    Uses protocol_config for method, path, headers. Defaults to GET with
    tool_name-derived path suffix and query params from arguments.
    Supports automatic retry for GET/HEAD methods.
    """
    base_url = instance["mcp_endpoint"].rstrip("/")
    cfg = instance.get("protocol_config", {})

    if err := _check_ssrf(base_url, tool_name):
        return err

    path = cfg.get("path", "")
    if not path:
        parts = tool_name.split(".", 1)
        path = "/" + (parts[1] if len(parts) > 1 else parts[0])

    method = cfg.get("method", "GET").upper()
    headers = cfg.get("headers", {})
    url = f"{base_url}{path}"

    max_retries = cfg.get("retries", 2) if method in ("GET", "HEAD") else 0

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            client = _get_client()
            if method in ("POST", "PUT", "PATCH"):
                resp = await client.request(method, url, json=arguments, headers=headers)
            else:
                resp = await client.request(method, url, params=arguments, headers=headers)
            try:
                body = resp.json()
            except Exception:
                body = {"_body": resp.text[:2000]}
            if not isinstance(body, dict):
                body = {"result": body}
            response_body: dict[str, object] = dict(body)
            response_body["http_status"] = resp.status_code
            resp.raise_for_status()
            return response_body
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if attempt < max_retries and status in (408, 429, 500, 502, 503, 504):
                last_error = e
                continue
            return {"status": "error", "http_status": status, "error": f"REST call failed: {str(e)[:200]}"}
        except Exception as e:
            if attempt < max_retries:
                last_error = e
                continue
            return {"status": "error", "error": f"REST call failed: {str(e)[:200]}"}

    return {"status": "error", "error": f"REST call failed after {max_retries + 1} attempts: {str(last_error)[:200]}"}


# ── gRPC handler ────────────────────────────────────────────────────


async def _call_grpc(tool_name: str, arguments: dict, instance: dict) -> dict:
    """Execute a gRPC call. Requires grpcio + compiled proto stub."""
    try:
        grpc = importlib.import_module("grpc")
        aio = importlib.import_module("grpc.aio")
    except ImportError:
        return {"status": "error", "error": "grpcio not installed. Run: pip install grpcio grpcio-tools"}

    cfg = instance.get("protocol_config", {})
    endpoint = instance["mcp_endpoint"]
    host = cfg.get("host", endpoint.replace("grpc://", "").rstrip("/"))
    if ":" not in host:
        return {"status": "error", "error": f"gRPC host:port required, got: {host}"}

    stub_module = cfg.get("stub_module", "")
    request_class = cfg.get("request_class", "")
    if not stub_module or not request_class:
        return {
            "status": "error",
            "error": "gRPC requires compiled proto stub. "
            "Set protocol_config.stub_module and .request_class, "
            "or use REST/MCP protocol instead.",
        }

    try:
        mod = importlib.import_module(stub_module)
        stub_cls_name = stub_module.split(".")[-1] + "Stub"
        stub_cls = getattr(mod, stub_cls_name, None)
        req_cls = getattr(mod, request_class, None)
        if not stub_cls or not req_cls:
            return {"status": "error", "error": f"Stub class not found in {stub_module}"}

        async with aio.insecure_channel(host) as channel:
            stub = stub_cls(channel)
            method_name = cfg.get("grpc_method", tool_name).split("/")[-1]
            handler = getattr(stub, method_name, None)
            if not handler:
                return {"status": "error", "error": f"Method {method_name} not found on stub"}
            req = req_cls(**arguments) if isinstance(arguments, dict) else req_cls()
            resp = await handler(req)
            return {"status": "ok", "result": str(resp)[:2000]}
    except grpc.aio.AioRpcError as e:
        return {"status": "error", "error": f"gRPC: {e.code()} - {e.details()}"}
    except Exception as e:
        return {"status": "error", "error": f"gRPC call failed: {str(e)[:200]}"}


# ── WebSocket handler ───────────────────────────────────────────────


async def _call_ws(tool_name: str, arguments: dict, instance: dict) -> dict:
    """Execute a WebSocket call for request-response pattern."""
    try:
        import websockets
    except ImportError:
        return {"status": "error", "error": "websockets not installed. Run: pip install websockets"}

    ws_url = instance["mcp_endpoint"]
    if not ws_url.startswith(("ws://", "wss://")):
        return {"status": "error", "error": "Invalid WebSocket URL"}

    cfg = instance.get("protocol_config", {})
    path = cfg.get("path", "")
    if path:
        ws_url = ws_url.rstrip("/") + "/" + path.lstrip("/")

    timeout = cfg.get("timeout", 10)
    send_payload = cfg.get("send_json") or arguments
    headers = cfg.get("headers", {})

    try:
        async with websockets.connect(ws_url, extra_headers=headers, open_timeout=timeout) as ws:
            if send_payload:
                await ws.send(_json.dumps(send_payload) if not isinstance(send_payload, str) else send_payload)
            resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
            try:
                return _json.loads(resp)
            except Exception:
                return {"status": "ok", "result": resp}
    except TimeoutError:
        return {"status": "error", "error": f"WebSocket timeout after {timeout}s"}
    except websockets.exceptions.InvalidURI as e:
        return {"status": "error", "error": f"Invalid WebSocket URI: {str(e)}"}
    except Exception as e:
        return {"status": "error", "error": f"WebSocket call failed: {str(e)[:200]}"}
