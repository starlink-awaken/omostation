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
    get_service,
    invoke_stdio,
    list_domains,
    list_services,
    normalize_bos_uri,
    parse_bos_uri,
    protocol_self_check,
    resolve_bos_uri,
)
from agora.mcp.resolver.pool import ProcessPool
from agora.mcp.resolver.pool import get_pool as _get_pool
from agora.mcp.resolver.services import (
    BOS_URI_PATTERN,
    POC_SERVICES,
    BosService,
    _with_uv_package,
)

_pool = _get_pool()

# Re-export get_pool for backward compat
get_pool = _get_pool

_log = logging.getLogger(__name__)

# ── 兼容导出 ──────────────────────────────────────────
__all__ = [
    "BOS_URI_PATTERN",
    "POC_SERVICES",
    "BosService",
    "ProcessPool",
    "StdioAdapter",
    "_memory_all_search",
    "_memory_vault_search",
    "_meta_discover",
    "_pool",
    "_sharedbrain_bridge_recall_entity",
    "_with_uv_package",
    "get_pool",
    "get_service",
    "get_stdio_adapter",
    "invoke_stdio",
    "list_domains",
    "list_services",
    "normalize_bos_uri",
    "parse_bos_uri",
    "protocol_self_check",
    "resolve_bos_uri",
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

    _log.info(
        "[MemorySpine] Aggregating search for: %s (Swarm: %s)",
        query,
        bool(proxy_manager),
    )

    # 待检索的子目标 — 只调用实际注册的服务，避免对不存在的 URI 发请求
    candidate_targets = [
        "bos://memory/kos/search",
        "bos://memory/gbrain/search",
        "bos://memory/vault/search",
    ]
    targets = [t for t in candidate_targets if get_service(t) is not None]
    if not targets:
        return {
            "status": "error",
            "error": "no_search_backend_available",
            "query": query,
        }

    import asyncio

    async def _safe_call(uri: str) -> dict:
        try:
            # 传递 proxy_manager 以支持跨节点路由，增加 5s 超时控制
            import asyncio

            res = await asyncio.wait_for(
                resolve_bos_uri(
                    uri, {"query": query, "limit": limit}, proxy_manager=proxy_manager
                ),
                timeout=5.0,
            )
            return {"uri": uri, "data": res}
        except Exception as e:  # defensive fallback
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
            hits = raw_res.get("results", []) if isinstance(raw_res, dict) else raw_res
        else:
            hits = raw_res if isinstance(raw_res, list) else []

        for h in hits:
            # 注入来源标签
            h["_source"] = uri
            aggregated.append(h)

    # 按照相关性分数重排序 (如果存在)
    aggregated.sort(key=lambda x: x.get("score", 0), reverse=True)
    top_results = aggregated[:limit]

    # Phase 9: Quality Audit/Partitioning
    # 引入对质量审计路由的并发调用，基于置信度阈值过滤聚合结果。
    audit_uri = "bos://governance/quality/audit"
    if top_results and get_service(audit_uri) is not None:

        async def _audit(res: dict) -> dict | None:
            try:
                # 调用轻量级评价模型或启发式审计器
                audit_res = await asyncio.wait_for(
                    resolve_bos_uri(
                        audit_uri,
                        {"text": res.get("snippet", str(res)[:500]), "query": query},
                        proxy_manager=proxy_manager,
                    ),
                    timeout=2.0,
                )

                # 提取评分 (支持从 ok 包装中提取)
                confidence = 1.0
                if isinstance(audit_res, dict):
                    inner = audit_res.get("result", audit_res)
                    confidence = inner.get("confidence", 1.0)

                # 过滤极低置信度的结果 (如 0.3)
                if confidence < 0.3:
                    _log.debug(
                        "[MemorySpine] Filtering low confidence hit (%s): %s",
                        confidence,
                        res.get("snippet", "")[:30],
                    )
                    return None

                res["_audit_score"] = confidence
                return res
            except Exception as e:  # defensive fallback
                _log.debug("[MemorySpine] Audit failed for hit: %s", e)
                return res

        # 并行并发审计
        audited_results = await asyncio.gather(*[_audit(r) for r in top_results])
        valid_results = [r for r in audited_results if r is not None]

        # ── Phase 15: Knowledge Deduplication ──
        seen_hashes = set()
        deduped = []
        import hashlib

        for res in valid_results:
            snippet = res.get("snippet", str(res))
            # 针对 snippet 或 content 计算简易哈希
            content_hash = hashlib.md5(snippet.strip().encode("utf-8")).hexdigest()
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                deduped.append(res)
            else:
                _log.debug(
                    "[MemorySpine] Deduplicated hit from %s",
                    res.get("_source", "unknown"),
                )

        top_results = deduped
        # 根据审计分数再次微调排序
        top_results.sort(key=lambda x: x.get("_audit_score", 0), reverse=True)

    return {
        "status": "ok",
        "query": query,
        "total_hits": len(top_results),
        "result": top_results,
        "sources_searched": targets,
    }


async def _memory_vault_search(args: dict | None = None) -> list[dict]:
    """L4 Vault 本地知识库高性能搜索 (ripgrep 实现)."""
    args = args or {}
    query = args.get("query")
    limit = args.get("limit", 10)

    if not query:
        return []

    cards_dir = Path(_WS) / "data" / "cards"
    results = []

    if not cards_dir.exists():
        return []

    import subprocess

    try:
        # 使用 ripgrep (rg) 进行高性能搜索
        # -i: 忽略大小写, -l: 只列出文件名, --max-count: 限制每个文件的匹配数
        cmd = ["rg", "-i", "-l", "--max-count", "1", query, str(cards_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

        filenames = proc.stdout.strip().split("\n")
        count = 0
        for fname in filenames:
            if not fname or count >= limit:
                break

            f = Path(fname)
            try:
                content = f.read_text(encoding="utf-8")
                # 寻找第一个匹配行的片段
                snippet = ""
                for line in content.splitlines():
                    if query.lower() in line.lower():
                        snippet = line.strip()[:200] + "..."
                        break

                results.append(
                    {
                        "id": f.stem,
                        "title": f.name,
                        "path": str(f.relative_to(_WS)),
                        "score": 0.9 if query.lower() in f.name.lower() else 0.7,
                        "snippet": snippet or (content[:200] + "..."),
                    }
                )
                count += 1
            except Exception:  # defensive fallback
                continue
    except Exception as e:  # defensive fallback
        _log.error("[VaultSearch] ripgrep failed: %s", e)
        return []

    return results


async def _meta_discover(args: dict | None = None) -> dict:
    """发现并枚举系统所有可用的 BOS 路由。"""
    from agora.mcp.bos_router import bos_router

    return {
        "total_routes": len(bos_router.list_all()),
        "routes": bos_router.list_all(),
        "domains": list_domains(),
    }


async def _sharedbrain_bridge_recall_entity(
    args: dict | None = None, proxy_manager: Any | None = None
) -> dict:
    """SharedBrain Bridge 实体召回 (P36-W1 GAP 占位实现).

    当前为注册表补全占位：返回空结果 + ok，真实召回逻辑待 SharedBrain
    数据层接入后替换。
    """
    args = args or {}
    entity_id = args.get("entity_id", "")
    return {
        "status": "ok",
        "entity_id": entity_id,
        "recalled": [],
        "note": "sharedbrain-bridge recall placeholder",
    }
