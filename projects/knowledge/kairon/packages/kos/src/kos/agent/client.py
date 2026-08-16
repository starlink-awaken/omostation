#!/usr/bin/env python3
# ruff: noqa
"""
KOS Agent SDK — AI Agent 知识后端 SDK

为 AI Agent 提供统一的 KOS 知识操作接口，
封装 MCP 调用、上下文工程、订阅管理。

Usage:
    from kos.agent import KosAgentClient

    client = KosAgentClient()

    # 智能问答
    answer = client.ask("数据治理的最佳实践是什么？")

    # 构建上下文
    context = client.build_context("数字化转型", mode="detailed")

    # 搜索
    results = client搜索("平台", limit=5)

    # 订阅主题
    sub = client.subscribe("数字化平台")

    # 验证声明
    verification = client.verify("夏明星参与了数字化平台项目")
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class KosAgentClient:
    """KOS Agent SDK — AI Agent 知识后端客户端。

    提供高层次的知识操作 API，封装底层检索、上下文、订阅逻辑。
    """

    def __init__(self, db_path: str | None = None, subscriber_id: str = "default-agent"):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self.subscriber_id = subscriber_id

    # ── 智能问答 ────────────────────────────────────────────

    def ask(
        self,
        question: str,
        mode: str = "balanced",
        persona: str | None = None,
    ) -> dict[str, Any]:
        """基于知识库回答问题。

        检索相关知识并组装为 LLM 可消费的上下文。

        Args:
            question: 问题。
            mode: 上下文模式 concise|balanced|detailed。
            persona: Agent 角色。

        Returns:
            包含 context、sources、prompt 的 dict。
        """
        from kos.context_engine import ContextEngine

        engine = ContextEngine(self.db_path)
        ctx = engine.build_context(question, mode=mode, persona=persona)
        prompt = engine._format_prompt(ctx)
        engine.close()

        return {
            "question": question,
            "context": ctx,
            "prompt": prompt,
            "sources_count": ctx["sources_count"],
            "total_tokens": ctx["total_tokens"],
        }

    # ── 上下文构建 ──────────────────────────────────────────

    def build_context(
        self,
        query: str,
        mode: str = "balanced",
        persona: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """为任务构建上下文。

        Args:
            query: 查询/任务。
            mode: 上下文模式。
            persona: 角色。
            max_tokens: token 限制。

        Returns:
            上下文 dict。
        """
        from kos.context_engine import ContextEngine

        engine = ContextEngine(self.db_path)
        ctx = engine.build_context(query, mode=mode, persona=persona, max_tokens=max_tokens)
        engine.close()
        return ctx

    # ── 搜索 ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 10,
    ) -> dict[str, Any]:
        """搜索知识库。

        Args:
            query: 搜索查询。
            mode: 搜索模式 keyword|semantic|graph|hybrid。
            limit: 最大结果数。

        Returns:
            搜索结果。
        """
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine(self.db_path)
        result = engine.search(query, mode=mode, limit=limit)
        engine.close()
        return result

    # ── 实体探索 ────────────────────────────────────────────

    def explore_entity(self, entity_id: str) -> dict[str, Any]:
        """探索实体详情。

        Args:
            entity_id: 实体 ID。

        Returns:
            实体卡片。
        """
        from kos.ontology.engine import card

        return card(entity_id)

    def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        """搜索实体。

        Args:
            query: 查询。
            limit: 最大结果数。

        Returns:
            实体列表。
        """
        conn = get_connection(self.db_path)
        rows = conn.execute(
            """SELECT entity_id, label, entity_type, description
               FROM kos_entities
               WHERE label LIKE ? OR description LIKE ?
               LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        conn.close()

        return [
            {
                "entity_id": r["entity_id"],
                "label": r["label"],
                "type": r["entity_type"],
                "description": r["description"],
            }
            for r in rows
        ]

    # ── 声明验证 ────────────────────────────────────────────

    def verify(self, claim: str) -> dict[str, Any]:
        """验证声明是否被知识库支持。

        Args:
            claim: 要验证的声明。

        Returns:
            验证结果。
        """
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine(self.db_path)
        result = engine.search(claim, mode="hybrid", limit=10)
        engine.close()

        evidence = []
        for r in result.get("results", []):
            evidence.append(
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", "")[:300],
                    "source": r.get("source", ""),
                }
            )

        return {
            "claim": claim,
            "evidence_count": len(evidence),
            "evidence": evidence,
            "verdict": "supported" if len(evidence) >= 3 else ("partial" if len(evidence) >= 1 else "no_evidence"),
        }

    # ── 订阅管理 ────────────────────────────────────────────

    def subscribe(self, topic: str, threshold: float = 0.5) -> dict[str, Any]:
        """订阅主题。

        Args:
            topic: 主题/关键词。
            threshold: 匹配阈值。

        Returns:
            订阅信息。
        """
        from kos.agent.subscription import SubscriptionService

        service = SubscriptionService(self.db_path)
        return service.subscribe(topic, self.subscriber_id, threshold)

    def unsubscribe(self, sub_id: str) -> dict[str, Any]:
        """取消订阅。"""
        from kos.agent.subscription import SubscriptionService

        service = SubscriptionService(self.db_path)
        return service.unsubscribe(sub_id)

    def check_subscription(self, sub_id: str) -> dict[str, Any]:
        """检查订阅的新匹配。"""
        from kos.agent.subscription import SubscriptionService

        service = SubscriptionService(self.db_path)
        return service.check_matches(sub_id)

    def list_subscriptions(self) -> list[dict]:
        """列出所有订阅。"""
        from kos.agent.subscription import SubscriptionService

        service = SubscriptionService(self.db_path)
        return service.list_subscriptions(self.subscriber_id)

    # ── 系统状态 ────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """获取系统状态。"""
        from kos.monitoring import KosMonitor

        monitor = KosMonitor(self.db_path)
        return monitor.index_health()

    def stats(self) -> dict[str, Any]:
        """获取知识库统计。"""
        conn = get_connection(self.db_path)

        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        entity_count = conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM kos_relations").fetchone()[0]

        zones = conn.execute(
            "SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone ORDER BY cnt DESC LIMIT 5"
        ).fetchall()

        conn.close()

        return {
            "documents": doc_count,
            "entities": entity_count,
            "relations": relation_count,
            "top_zones": {z["zone"]: z["cnt"] for z in zones},
        }


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Agent SDK CLI")
    parser.add_argument(
        "action",
        choices=["ask", "search", "context", "explore", "verify", "subscribe", "status", "stats"],
        help="Action",
    )
    parser.add_argument("--query", help="Query")
    parser.add_argument("--mode", default="balanced", choices=["concise", "balanced", "detailed"])
    parser.add_argument("--persona", help="Persona")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--subscriber", default="cli-agent", help="Subscriber ID")
    args = parser.parse_args()

    client = KosAgentClient(subscriber_id=args.subscriber)

    if args.action == "ask":
        if not args.query:
            print("Error: --query required")
            return
        result = client.ask(args.query, mode=args.mode, persona=args.persona)
    elif args.action == "search":
        if not args.query:
            print("Error: --query required")
            return
        result = client.search(args.query, mode="hybrid", limit=args.limit)
    elif args.action == "context":
        if not args.query:
            print("Error: --query required")
            return
        result = client.build_context(args.query, mode=args.mode, persona=args.persona)
    elif args.action == "explore":
        if not args.query:
            print("Error: --query required")
            return
        result = client.explore_entity(args.query)
    elif args.action == "verify":
        if not args.query:
            print("Error: --query required")
            return
        result = client.verify(args.query)
    elif args.action == "subscribe":
        if not args.query:
            print("Error: --query required")
            return
        result = client.subscribe(args.query)
    elif args.action == "status":
        result = client.status()
    elif args.action == "stats":
        result = client.stats()
    else:
        result = {"error": "Unknown action"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
