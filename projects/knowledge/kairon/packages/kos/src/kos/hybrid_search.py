#!/usr/bin/env python3
# ruff: noqa
"""
KOS Hybrid Search Engine — 统一混合检索引擎

将 FTS5 关键词搜索、LanceDB 向量语义搜索、图谱遍历三路检索
通过 RRF (Reciprocal Rank Fusion) 融合为统一结果。

Usage:
    from kos.hybrid_search import HybridSearchEngine

    engine = HybridSearchEngine()

    # 混合检索 (自动选择最优路径)
    result = engine.search("数据治理", mode="hybrid", limit=10)

    # 仅关键词
    result = engine.search("数据治理", mode="keyword", limit=10)

    # 仅语义
    result = engine.search("数据治理", mode="semantic", limit=10)

    # 带上下文配置
    result = engine.search("数据治理", context={"mode": "detailed", "persona": "架构师"})

检索模式:
    keyword  - FTS5 全文检索 (jieba中文分词 + 提升排序)
    semantic - LanceDB 向量语义检索 (Qwen3-Embedding-8B)
    graph    - 图谱实体遍历 (多跳关系)
    hybrid   - RRF 融合三路结果 (默认)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class HybridSearchEngine:
    """统一混合检索引擎。

    将多种检索策略 (关键词/语义/图谱) 通过 RRF 融合，
    为 AI Agent 提供统一的知识检索入口。
    """

    def __init__(self, db_path: str | None = None, cache: "SearchCache | None" = None):  # type: ignore[reportUndefinedVariable]
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self._conn = None
        self._cache = cache

    @property
    def cache(self) -> "SearchCache | None":  # type: ignore[reportUndefinedVariable]
        if self._cache is None:
            from kos.cache import SearchCache

            self._cache = SearchCache(db_path=self.db_path)
        return self._cache

    @cache.setter
    def cache(self, value: "SearchCache | None") -> None:  # type: ignore[reportUndefinedVariable]
        self._cache = value

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    # ── 搜索入口 ────────────────────────────────────────────

    def search(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 10,
        context: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """统一搜索入口。

        Args:
            query: 搜索查询。
            mode: 检索模式: keyword | semantic | graph | hybrid
            limit: 最大返回结果数。
            context: 上下文配置 {"mode": "concise|balanced|detailed", "persona": "...", "domain": "..."}
            use_cache: 是否使用缓存 (默认 True)。

        Returns:
            搜索结果 dict，包含 results、query_plan、sources 等。
        """
        t0 = time.monotonic()

        if not query or not query.strip():
            return {"query": query, "results": [], "count": 0, "error": "empty query"}

        query = query.strip()

        # 0. 查缓存
        if use_cache and self._cache is not False:
            cached = self.cache.get(query, mode, limit)  # type: ignore[reportOptionalMemberAccess]
            if cached is not None:
                cached["elapsed_ms"] = round((time.monotonic() - t0) * 1000, 2)
                return cached

        # 1. 查询计划: 决定走哪些检索路径
        plan = self._plan_query(query, context)
        plan["mode"] = mode

        # 2. 多路检索
        results: dict[str, list[dict]] = {}

        if mode == "keyword":
            results["keyword"] = self._fts5_search(query, plan["keyword_limit"])
            if plan["needs_graph"]:
                results["graph"] = self._graph_search(query, plan["graph_limit"])
        elif mode == "semantic":
            results["semantic"] = self._vector_search(query, plan["semantic_limit"])
        elif mode == "graph":
            results["graph"] = self._graph_search(query, plan["graph_limit"])
        else:  # hybrid
            if plan["needs_keyword"]:
                results["keyword"] = self._fts5_search(query, plan["keyword_limit"])
            if plan["needs_semantic"]:
                results["semantic"] = self._vector_search(query, plan["semantic_limit"])
            if plan["needs_graph"]:
                results["graph"] = self._graph_search(query, plan["graph_limit"])

        # 3. RRF 融合
        fused = self._reciprocal_rank_fusion(results, plan)

        # 4. 结果后处理
        final = self._post_process(fused, limit, context)

        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

        result = {
            "query": query,
            "mode": mode,
            "results": final,
            "count": len(final),
            "query_plan": plan,
            "sources": {k: len(v) for k, v in results.items()},
            "elapsed_ms": elapsed_ms,
        }

        # 写入缓存
        if use_cache and self._cache is not False and final:
            self.cache.set(  # type: ignore[reportOptionalMemberAccess]
                query,
                mode,
                final,
                limit,
                {
                    "sources": result["sources"],
                    "elapsed_ms": elapsed_ms,
                    "query_plan": plan,
                    "count": len(final),
                },
            )

        return result

    # ── 查询计划 ────────────────────────────────────────────

    def _plan_query(self, query: str, context: dict[str, Any] | None) -> dict[str, Any]:
        """动态查询计划——决定走哪些检索路径和参数。"""
        complexity = len(query.split())
        is_chinese = bool(re.search(r"[一-鿿]", query))

        # 上下文模式决定检索预算
        ctx_mode = (context or {}).get("mode", "balanced")
        budgets = {
            "concise": {"limit": 3, "snippet": 200},
            "balanced": {"limit": 7, "snippet": 300},
            "detailed": {"limit": 15, "snippet": 500},
        }
        budget = budgets.get(ctx_mode, budgets["balanced"])

        return {
            "needs_keyword": True,  # 关键词总是需要
            "needs_semantic": len(query) > 2 and complexity >= 1,  # 有效查询做语义
            "needs_graph": self._has_entity_match(query),  # 实体匹配时走图谱
            "keyword_limit": budget["limit"] * 3,
            "semantic_limit": budget["limit"] * 3,
            "graph_limit": budget["limit"] * 2,
            "snippet_length": budget["snippet"],
            "complexity": complexity,
            "is_chinese": is_chinese,
            "context_mode": ctx_mode,
        }

    def _has_entity_match(self, query: str) -> bool:
        """检查查询是否匹配已知实体。"""
        try:
            rows = self.conn.execute(
                "SELECT 1 FROM kos_entities WHERE label LIKE ? OR ? LIKE '%' || label || '%' LIMIT 1",
                (f"%{query}%", query),
            ).fetchall()
            return len(rows) > 0
        except sqlite3.OperationalError:
            return False

    # ── FTS5 关键词检索 ─────────────────────────────────────

    def _fts5_search(self, query: str, limit: int) -> list[dict]:
        """FTS5 全文检索，含提升排序。"""
        try:
            # jieba 分词处理中文查询
            match_query = self._prepare_fts_query(query)

            rows = self.conn.execute(
                f"""
                WITH scored AS (
                    SELECT d.doc_id, d.title, d.kind, d.zone, d.status,
                           d.canonical_path, d.trust_level, d.updated_at,
                           d.metadata_json,
                           snippet(documents_fts, 1, '<b>', '</b>', '...', 80) AS snippet,
                           f.rank AS fts_rank,
                           CASE WHEN d.canonical_path LIKE '%CARDS/%' THEN 5.0 ELSE 0.0 END AS cards_boost,
                           CASE
                               WHEN d.body LIKE '%author: 夏明星%'
                                    OR d.body LIKE '%author_alias: xiamingxing%'
                                    OR d.metadata_json LIKE '%夏明星%'
                                    OR d.metadata_json LIKE '%xiamingxing%'
                               THEN 10.0 ELSE 0.0
                           END AS author_boost,
                           CASE WHEN EXISTS (
                               SELECT 1 FROM kos_entity_docs ed WHERE ed.doc_id = d.doc_id
                           ) THEN 3.0 ELSE 0.0 END AS entity_boost,
                           CASE
                               WHEN d.updated_at >= date('now', '-7 days') THEN 2.0
                               WHEN d.updated_at >= date('now', '-30 days') THEN 1.0
                               ELSE 0.0
                           END AS freshness_boost
                    FROM documents_fts f
                    JOIN documents d ON f.doc_id = d.doc_id
                    WHERE documents_fts MATCH ?
                )
                SELECT doc_id, title, kind, zone, status, canonical_path,
                       trust_level, updated_at, snippet, metadata_json
                FROM scored
                ORDER BY (fts_rank - cards_boost - author_boost - entity_boost - freshness_boost) ASC,
                         updated_at DESC
                LIMIT ?
                """,
                (match_query, limit),
            ).fetchall()

            return [
                {
                    "doc_id": r["doc_id"],
                    "title": r["title"],
                    "zone": r["zone"],
                    "kind": r["kind"],
                    "canonical_path": r["canonical_path"],
                    "snippet": r["snippet"],
                    "updated_at": r["updated_at"],
                    "source": "keyword",
                }
                for r in rows
            ]
        except sqlite3.OperationalError:
            return []

    def _prepare_fts_query(self, query: str) -> str:
        """为 FTS5 准备查询字符串 (jieba 分词 + OR 连接)。"""
        # 如果已经有布尔运算符，保留原样
        if " OR " in query or " AND " in query:
            return query

        # 如果含中文，做 jieba 分词
        if re.search(r"[一-鿿]", query):
            try:
                from kos.indexer.engine import _tokenize_cn

                tokens = _tokenize_cn(query).split()
                if len(tokens) > 1:
                    return " OR ".join(t for t in tokens if t.strip())
            except ImportError:
                pass

        return query

    # ── 向量语义检索 ───────────────────────────────────────

    def _vector_search(self, query: str, limit: int) -> list[dict]:
        """LanceDB 向量语义检索。"""
        try:
            from kos.semantic import semantic_search, status
        except ImportError:
            return []

        # Check if vector index is built
        st = status()
        if st.get("status") != "active":
            return []

        try:
            result = semantic_search(query, limit=limit)
            results = result.get("results", [])
            for r in results:
                r["source"] = "semantic"
            return results
        except Exception:
            return []

    # ── 图谱遍历检索 ───────────────────────────────────────

    def _graph_search(self, query: str, limit: int) -> list[dict]:
        """基于实体关系的图谱遍历检索。"""
        try:
            # 1. 找到查询匹配的实体
            entities = self.conn.execute(
                """SELECT entity_id, label, entity_type FROM kos_entities
                   WHERE label LIKE ? OR ? LIKE '%' || label || '%'
                   LIMIT 5""",
                (f"%{query}%", query),
            ).fetchall()

            if not entities:
                return []

            # 2. 找到实体关联的文档
            results = []
            seen_doc_ids: set[str] = set()

            for ent in entities:
                doc_rows = self.conn.execute(
                    """SELECT d.doc_id, d.title, d.zone, d.kind,
                              d.canonical_path, d.updated_at, ed.relevance
                       FROM kos_entity_docs ed
                       JOIN documents d ON ed.doc_id = d.doc_id
                       WHERE ed.entity_id = ?
                       ORDER BY ed.relevance DESC LIMIT 5""",
                    (ent["entity_id"],),
                ).fetchall()

                for r in doc_rows:
                    doc_id = r["doc_id"]
                    if doc_id not in seen_doc_ids:
                        seen_doc_ids.add(doc_id)
                        results.append(
                            {
                                "doc_id": doc_id,
                                "title": r["title"],
                                "zone": r["zone"],
                                "kind": r["kind"],
                                "canonical_path": r["canonical_path"],
                                "updated_at": r["updated_at"],
                                "relevance": r["relevance"],
                                "matched_entity": ent["label"],
                                "source": "graph",
                            }
                        )

                    if len(results) >= limit:
                        break

                if len(results) >= limit:
                    break

            return results[:limit]

        except sqlite3.OperationalError:
            return []

    # ── RRF 融合 ────────────────────────────────────────────

    def _reciprocal_rank_fusion(
        self,
        results: dict[str, list[dict]],
        plan: dict[str, Any],
    ) -> list[dict]:
        """Reciprocal Rank Fusion 多路结果融合。

        不同检索源的结果通过 RRF 公式合并：
        score(d) = Σ w_s / (k + rank_s(d))

        k=60 避免对低排名结果的过度奖励。
        """
        k = 60
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        weights = {
            "keyword": 1.0,
            "semantic": 1.2,  # 语义结果给予轻微加权
            "graph": 0.8,  # 图谱结果作为补充
        }

        for source, source_results in results.items():
            weight = weights.get(source, 1.0)
            for rank, doc in enumerate(source_results):
                doc_id = doc["doc_id"]
                docs[doc_id] = doc
                scores[doc_id] = scores.get(doc_id, 0) + weight / (k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [{**docs[doc_id], "_rrf_score": round(score, 4)} for doc_id, score in ranked]

    # ── 结果后处理 ──────────────────────────────────────────

    def _post_process(
        self,
        results: list[dict],
        limit: int,
        context: dict[str, Any] | None,
    ) -> list[dict]:
        """结果后处理: 去重、裁剪、格式化。"""
        seen_paths: set[str] = set()
        final: list[dict] = []

        for doc in results:
            path = doc.get("canonical_path", "")
            if path in seen_paths:
                continue
            seen_paths.add(path)

            # 清理 snippet 中的 HTML 标签
            snippet = doc.get("snippet", "")
            clean_snippet = re.sub(r"</?b>", "", snippet)
            doc["snippet"] = clean_snippet

            final.append(doc)
            if len(final) >= limit:
                break

        return final

    # ── 工具方法 ────────────────────────────────────────────

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "HybridSearchEngine":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Hybrid Search Engine")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--mode",
        default="hybrid",
        choices=["keyword", "semantic", "graph", "hybrid"],
        help="Search mode (default: hybrid)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument(
        "--context-mode",
        default="balanced",
        choices=["concise", "balanced", "detailed"],
        help="Context mode (default: balanced)",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    engine = HybridSearchEngine()
    result = engine.search(
        args.query,
        mode=args.mode,
        limit=args.limit,
        context={"mode": args.context_mode},
    )
    engine.close()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"\n🔍 {result['query']}  ·  {result['mode']}  ·  {result['count']} results  ·  {result['elapsed_ms']}ms\n"
        )
        for i, r in enumerate(result["results"], 1):
            title = r.get("title", "Untitled")[:60]
            path = r.get("canonical_path", "")
            if "::" in path:
                short_path = "::".join(path.split("::")[1:])
            else:
                short_path = path
            if len(short_path) > 55:
                short_path = "…" + short_path[-54:]
            source = r.get("source", "?")
            print(f"  {i}. [{source}] {title}")
            print(f"     {short_path}")
            snippet = r.get("snippet", "")
            if snippet:
                print(f"     {snippet[:120]}")
            print()


if __name__ == "__main__":
    main()
