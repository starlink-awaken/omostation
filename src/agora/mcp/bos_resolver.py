"""BOS URI 解析器 — agora 侧 (已拆分为 resolver/ 包).

此文件为向后兼容转发层。新代码请直接 import resolver 子模块。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from agora.mcp.resolver.adapter import StdioAdapter, get_stdio_adapter
from agora.mcp.resolver.api import (
    normalize_bos_uri,
    parse_bos_uri,
    list_services,
    get_service,
    list_domains,
    invoke_stdio,
    protocol_self_check,
    resolve_bos_uri,  # noqa: F401 — re-exported in __all__
)
from agora.mcp.resolver.pool import ProcessPool, get_pool as _get_pool  # noqa: F401
from agora.mcp.resolver.services import BosService, POC_SERVICES, _with_uv_package, BOS_URI_PATTERN  # noqa: F401

_pool = _get_pool()

# Re-export get_pool for backward compat
get_pool = _get_pool

_log = logging.getLogger(__name__)

# ── 兼容导出 ──────────────────────────────────────────
__all__ = [
    "BosService",
    "POC_SERVICES",
    "ProcessPool",
    "StdioAdapter",
    "normalize_bos_uri",
    "parse_bos_uri",
    "list_services",
    "get_service",
    "list_domains",
    "invoke_stdio",
    "protocol_self_check",
    "get_pool",
    "get_stdio_adapter",
    "_with_uv_package",
    "resolve_bos_uri",
    "BOS_URI_PATTERN",
    "_pool",
    "_memory_all_search",
    "_memory_vault_search",
    "_meta_discover",
]

# ── 路径常量 (保持向后兼容) ────────────────────────────
_WS = os.environ.get("WORKSPACE_ROOT") or str(Path.home() / "Workspace")
KAIRON_ROOT = Path(_WS) / "projects" / "kairon"
METAOS_ROOT = Path(_WS) / "projects" / "metaos"
OMOSTATION_ROOT = Path(_WS)


# ── Internal Service Implementations (Memory Spine) ──


async def _memory_all_search(
    args: dict | None = None, proxy_manager: Any | None = None
) -> dict:
    """[Phase 2] 记忆脊聚合搜索: 同时检索 KOS、gbrain 与 Vault (Swarm 增强版)。"""
    args = args or {}
    query = args.get("query", "")
    limit = args.get("limit", 10)

    if not query:
        return {"status": "error", "error": "missing_query"}

    _log.info("[MemorySpine] Aggregating search for: %s (Swarm: %s)", query, bool(proxy_manager))

    # 待检索的子目标
    targets = [
        "bos://memory/kos/search",
        "bos://memory/gbrain/search",
        "bos://memory/vault/search",
    ]

    import asyncio

    async def _safe_call(uri: str) -> dict:
        try:
            # 传递 proxy_manager 以支持跨节点路由
            res = await resolve_bos_uri(
                uri, {"query": query, "limit": limit}, proxy_manager=proxy_manager
            )
            return {"uri": uri, "data": res}
        except Exception as e:
            return {"uri": uri, "error": str(e)}

    # 并行并发调用
    results = await asyncio.gather(*[_safe_call(t) for t in targets])

    # 聚合汇总
    aggregated = []
    for r in results:
        uri = r["uri"]
        if "error" in r:
            _log.warning("[MemorySpine] Target %s failed: %s", uri, r["error"])
            continue

        data = r["data"]
        # 标准化提取结果列表 (各后端输出格式略有不同)
        hits = []
        raw_res = data.get("result", []) if isinstance(data, dict) else []
        if uri == "bos://memory/kos/search":
            hits = raw_res if isinstance(raw_res, list) else []
        elif uri == "bos://memory/gbrain/search":
            hits = (
                raw_res.get("results", []) if isinstance(raw_res, dict) else raw_res
            )
        else:
            hits = raw_res if isinstance(raw_res, list) else []

        for h in hits:
            # 注入来源标签
            h["_source"] = uri
            aggregated.append(h)

    # 按照相关性分数重排序 (如果存在)
    aggregated.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "query": query,
        "total_hits": len(aggregated),
        "results": aggregated[:limit],
        "sources_searched": targets,
    }


async def _memory_vault_search(args: dict | None = None) -> list[dict]:
    """L4 Vault 本地知识库搜索 (模拟实现)."""
    args = args or {}
    query = (args.get("query") or "").lower()
    limit = args.get("limit", 10)

    cards_dir = Path(_WS) / "data" / "cards"
    results = []

    if not cards_dir.exists():
        return []

    # 简单全文检索模拟
    count = 0
    for f in cards_dir.glob("**/*.md"):
        if count >= limit:
            break
        try:
            content = f.read_text().lower()
            if query in content or query in f.name.lower():
                results.append(
                    {
                        "id": f.stem,
                        "title": f.name,
                        "path": str(f.relative_to(_WS)),
                        "score": 0.8 if query in f.name.lower() else 0.5,
                        "snippet": content[:200] + "...",
                    }
                )
                count += 1
        except Exception:
            continue

    return results


async def _meta_discover(args: dict | None = None) -> dict:
    """发现并枚举系统所有可用的 BOS 路由。"""
    from agora.mcp.bos_router import bos_router

    return {
        "total_routes": len(bos_router.list_all()),
        "routes": bos_router.list_all(),
        "domains": list_domains(),
    }
