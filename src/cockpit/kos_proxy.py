#!/usr/bin/env python3
# ruff: noqa
"""
Cockpit-KOS Proxy — cockpit 代理 KOS 搜索 API

在 cockpit Dashboard 中添加 /api/kos/* 代理路由，
将搜索请求转发到 KOS HybridSearchEngine。

Usage:
    # 在 cockpit dashboard_server.py 中集成:
    from cockpit.kos_proxy import init_kos_routes
    init_kos_routes(app)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ── FastAPI 代理路由 ─────────────────────────────────────

def init_kos_routes(app):
    """在 FastAPI app 上注册 KOS 代理路由。
    
    Args:
        app: FastAPI 应用实例。
    """
    from fastapi import HTTPException

    @app.get("/api/kos/search")
    async def kos_search(q: str, mode: str = "hybrid", limit: int = 10):
        """搜索知识库。
        
        Args:
            q: 搜索查询。
            mode: 检索模式 (keyword/semantic/graph/hybrid)。
            limit: 最大结果数。
        """
        try:
            from kos.hybrid_search import HybridSearchEngine
            engine = HybridSearchEngine()
            result = engine.search(q, mode=mode, limit=limit)
            engine.close()
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/kos/suggest")
    async def kos_suggest(prefix: str, limit: int = 8):
        """搜索建议。"""
        try:
            from kos.search_features import SearchFeatures
            features = SearchFeatures()
            result = features.suggest(prefix, limit=limit)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/kos/context")
    async def kos_context(q: str, mode: str = "balanced"):
        """构建 LLM 上下文。"""
        try:
            from kos.context_engine import ContextEngine
            engine = ContextEngine()
            result = engine.build_context(q, mode=mode)
            engine.close()
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/kos/verify")
    async def kos_verify(claim: str):
        """验证声明。"""
        try:
            from kos.hybrid_search import HybridSearchEngine
            engine = HybridSearchEngine()
            result = engine.search(claim, mode="hybrid", limit=10)
            engine.close()

            evidence = []
            for r in result.get("results", []):
                evidence.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", "")[:300],
                    "source": r.get("source", ""),
                })

            return {
                "claim": claim,
                "evidence_count": len(evidence),
                "evidence": evidence,
                "verdict": "supported" if len(evidence) >= 3 else ("partial" if len(evidence) >= 1 else "no_evidence"),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/kos/stats")
    async def kos_stats():
        """知识库统计。"""
        try:
            from kos.agent.client import KosAgentClient
            client = KosAgentClient()
            return client.stats()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/kos/health")
    async def kos_health():
        """健康检查。"""
        try:
            from kos.monitoring import KosMonitor
            monitor = KosMonitor()
            return monitor.index_health()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


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
    uvicorn.run(app, host="0.0.0.0", port=8766)
