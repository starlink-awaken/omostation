#!/usr/bin/env python3
# ruff: noqa
"""
Cockpit-KOS Proxy — cockpit 代理 KOS 搜索 API

在 cockpit Dashboard 中添加 /api/kos/* 代理路由，
将搜索请求转发到 KOS REST API 或 MCP Server。

架构: cockpit -(HTTP)-> KOS REST API / MCP Server
      loose coupling, 无直接 Python import

Usage:
    # 在 cockpit dashboard_server.py 中集成:
    from cockpit.kos_proxy import init_kos_routes
    init_kos_routes(app)

Environment:
    KOS_API_URL = http://localhost:8765  (KOS REST API)
    KOS_MCP_URL = http://localhost:8765  (KOS MCP Server)
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any

# KOS API URL (configurable via environment)
KOS_API_URL = os.environ.get("KOS_API_URL", "http://localhost:8770")  # 8766 reserved for KOS itself
KOS_MCP_URL = os.environ.get("KOS_MCP_URL", "http://localhost:8765")


def _kos_rest_call(method: str, path: str, data: dict | None = None) -> dict:
    """Make a REST call to KOS API."""
    url = f"{KOS_API_URL}{path}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"error": str(e), "url": url}
    except Exception as e:
        return {"error": str(e)}


def _url_encode_params(params: dict) -> str:
    """URL encode parameters."""
    import urllib.parse

    return urllib.parse.urlencode(params, encoding="utf-8", quote_via=urllib.parse.quote)


# ── FastAPI 代理路由 ─────────────────────────────────────


def init_kos_routes(app):
    """在 FastAPI app 上注册 KOS 代理路由。

    Args:
        app: FastAPI 应用实例。
    """
    from fastapi import HTTPException

    @app.get("/api/kos/search")
    async def kos_search(q: str, mode: str = "hybrid", limit: int = 10):
        """搜索知识库。"""
        params = {"q": q, "mode": mode, "limit": limit}
        result = _kos_rest_call("GET", f"/api/v1/search?{_url_encode_params(params)}")
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.get("/api/kos/suggest")
    async def kos_suggest(prefix: str, limit: int = 8):
        """搜索建议。"""
        params = {"prefix": prefix, "limit": limit}
        result = _kos_rest_call("GET", f"/api/v1/suggest?{_url_encode_params(params)}")
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.get("/api/kos/context")
    async def kos_context(q: str, mode: str = "balanced"):
        """构建 LLM 上下文。"""
        params = {"q": q, "mode": mode}
        result = _kos_rest_call("GET", f"/api/v1/context?{_url_encode_params(params)}")
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.post("/api/kos/verify")
    async def kos_verify(data: dict):
        """验证声明。"""
        result = _kos_rest_call("POST", "/api/v1/verify", data)
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.get("/api/kos/stats")
    async def kos_stats():
        """知识库统计。"""
        result = _kos_rest_call("GET", "/api/v1/stats")
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.get("/api/kos/health")
    async def kos_health():
        """健康检查。"""
        result = _kos_rest_call("GET", "/api/v1/health")
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.get("/api/kos/clusters")
    async def kos_clusters(q: str, limit: int = 10):
        """搜索 + 聚类。"""
        params = {"q": q, "limit": limit}
        result = _kos_rest_call("GET", f"/api/v1/clusters?{_url_encode_params(params)}")
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result


# ── 独立运行模式 ─────────────────────────────────────────


def create_kos_app():
    """创建独立的 KOS API 服务 (用于测试)。"""
    from fastapi import FastAPI

    app = FastAPI(title="KOS API", version="1.0.0")
    init_kos_routes(app)
    return app


if __name__ == "__main__":
    import uvicorn

    app = create_kos_app()
    uvicorn.run(app, host="0.0.0.0", port=8770)  # 8766 reserved for upstream KOS
