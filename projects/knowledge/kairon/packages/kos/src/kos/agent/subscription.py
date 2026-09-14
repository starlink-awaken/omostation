#!/usr/bin/env python3
# ruff: noqa
"""
KOS Knowledge Subscription — 知识订阅服务

允许 AI Agent 订阅特定主题，当有新文档匹配时自动推送通知。

Usage:
    from kos.agent.subscription import SubscriptionService

    service = SubscriptionService()

    # 订阅主题
    sub = service.subscribe("数字化平台", subscriber_id="agent-1")

    # 检查新匹配
    matches = service.check_matches("digital-platform-agent-1")

    # 取消订阅
    service.unsubscribe("digital-platform-agent-1")
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class SubscriptionService:
    """知识订阅服务。

    Agent 可以订阅特定主题，当新文档匹配时获得通知。
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")

    def subscribe(
        self,
        topic: str,
        subscriber_id: str,
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        """订阅一个主题。

        Args:
            topic: 订阅主题/关键词。
            subscriber_id: 订阅者标识 (如 agent ID)。
            threshold: 匹配阈值 (0-1)。

        Returns:
            订阅信息。
        """
        conn = get_connection(self.db_path)

        sub_id = hashlib.sha1(f"{topic}:{subscriber_id}".encode()).hexdigest()[:16]
        now = datetime.now().isoformat()

        conn.execute(
            """
            INSERT OR REPLACE INTO kos_subscriptions
            (sub_id, topic, subscriber_id, threshold, created_at, last_check, active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
            (sub_id, topic, subscriber_id, threshold, now, now),
        )

        conn.commit()
        conn.close()

        return {
            "sub_id": sub_id,
            "topic": topic,
            "subscriber_id": subscriber_id,
            "threshold": threshold,
            "active": True,
        }

    def unsubscribe(self, sub_id: str) -> dict[str, Any]:
        """取消订阅。"""
        conn = get_connection(self.db_path)
        conn.execute("UPDATE kos_subscriptions SET active=0 WHERE sub_id=?", (sub_id,))
        conn.commit()
        conn.close()
        return {"sub_id": sub_id, "active": False}

    def check_matches(self, sub_id: str) -> dict[str, Any]:
        """检查订阅的新匹配。"""
        conn = get_connection(self.db_path)

        # 获取订阅信息
        sub = conn.execute("SELECT * FROM kos_subscriptions WHERE sub_id=? AND active=1", (sub_id,)).fetchone()

        if not sub:
            conn.close()
            return {"error": "Subscription not found or inactive"}

        topic = sub["topic"]
        last_check = sub["last_check"]

        # 查找新文档 (last_check 之后索引的)
        try:
            new_docs = conn.execute(
                """
                SELECT d.doc_id, d.title, d.zone, d.canonical_path, d.updated_at
                FROM documents_fts f
                JOIN documents d ON f.doc_id = d.doc_id
                WHERE documents_fts MATCH ? AND d.updated_at > ?
                ORDER BY d.updated_at DESC LIMIT 10
            """,
                (topic, last_check),
            ).fetchall()
        except sqlite3.OperationalError:
            new_docs = []

        # 更新 last_check
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE kos_subscriptions SET last_check=? WHERE sub_id=?",
            (now, sub_id),
        )
        conn.commit()
        conn.close()

        return {
            "sub_id": sub_id,
            "topic": topic,
            "new_matches": len(new_docs),
            "documents": [
                {
                    "doc_id": d["doc_id"],
                    "title": d["title"],
                    "zone": d["zone"],
                    "canonical_path": d["canonical_path"],
                    "updated_at": d["updated_at"],
                }
                for d in new_docs
            ],
        }

    def list_subscriptions(self, subscriber_id: str | None = None) -> list[dict]:
        """列出订阅。"""
        conn = get_connection(self.db_path)

        if subscriber_id:
            rows = conn.execute(
                "SELECT * FROM kos_subscriptions WHERE subscriber_id=? AND active=1",
                (subscriber_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM kos_subscriptions WHERE active=1").fetchall()

        conn.close()

        return [
            {
                "sub_id": r["sub_id"],
                "topic": r["topic"],
                "subscriber_id": r["subscriber_id"],
                "threshold": r["threshold"],
                "created_at": r["created_at"],
                "last_check": r["last_check"],
            }
            for r in rows
        ]

    def check_all_subscriptions(self) -> list[dict]:
        """检查所有活跃订阅的新匹配。"""
        conn = get_connection(self.db_path)
        subs = conn.execute("SELECT sub_id FROM kos_subscriptions WHERE active=1").fetchall()
        conn.close()

        results = []
        for sub in subs:
            result = self.check_matches(sub["sub_id"])
            if result.get("new_matches", 0) > 0:
                results.append(result)

        return results

    @staticmethod
    def init_table(db_path: str) -> None:
        """初始化订阅表。"""
        conn = get_connection(db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kos_subscriptions (
                sub_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                subscriber_id TEXT NOT NULL,
                threshold REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                last_check TEXT NOT NULL,
                active INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_sub_subscriber
                ON kos_subscriptions(subscriber_id);
            CREATE INDEX IF NOT EXISTS idx_sub_active
                ON kos_subscriptions(active);
        """)
        conn.commit()
        conn.close()


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Knowledge Subscription")
    parser.add_argument(
        "action",
        choices=["subscribe", "unsubscribe", "check", "list", "check-all"],
        help="Action",
    )
    parser.add_argument("--topic", help="Topic to subscribe to")
    parser.add_argument("--subscriber", help="Subscriber ID")
    parser.add_argument("--sub-id", help="Subscription ID")
    parser.add_argument("--threshold", type=float, default=0.5, help="Match threshold")
    args = parser.parse_args()

    service = SubscriptionService()
    service.init_table(get_artifact_path("retrievalDatabase"))

    if args.action == "subscribe":
        if not args.topic or not args.subscriber:
            print("Error: --topic and --subscriber required")
            return
        result = service.subscribe(args.topic, args.subscriber, args.threshold)
    elif args.action == "unsubscribe":
        if not args.sub_id:
            print("Error: --sub-id required")
            return
        result = service.unsubscribe(args.sub_id)
    elif args.action == "check":
        if not args.sub_id:
            print("Error: --sub-id required")
            return
        result = service.check_matches(args.sub_id)
    elif args.action == "list":
        result = service.list_subscriptions(args.subscriber)
    elif args.action == "check-all":
        result = service.check_all_subscriptions()
    else:
        result = {"error": "Unknown action"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
