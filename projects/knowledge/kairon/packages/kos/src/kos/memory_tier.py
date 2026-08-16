#!/usr/bin/env python3
# ruff: noqa
"""
KOS Memory Tier — 三层记忆架构

实现分层记忆管理:
- L1 短期记忆: 当前会话 (内存 dict, 单次会话)
- L2 中期记忆: 搜索历史 (JSON 文件, LRU 淘汰)
- L3 长期记忆: 本体图谱 (SQLite, 永久)

Usage:
    from kos.memory_tier import MemoryTier

    memory = MemoryTier()

    # 记录搜索
    memory.record_search("数字化平台")

    # 获取历史
    history = memory.get_history(limit=10)

    # 获取热门查询
    popular = memory.get_popular(limit=5)

    # 获取完整上下文 (三层合并)
    context = memory.get_full_context("查询")
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class MemoryTier:
    """三层记忆架构管理。

    L1 (短期): 当前会话查询 (内存)
    L2 (中期): 搜索历史 (JSON 文件)
    L3 (长期): 本体图谱 (SQLite)
    """

    def __init__(
        self,
        history_path: str | None = None,
        max_history: int = 200,
    ):
        self.history_path = Path(history_path) if history_path else Path.home() / ".kos" / "search_history.json"
        self.max_history = max_history

        # L1: 短期记忆 (当前会话)
        self._session_queries: list[str] = []
        self._session_results: dict[str, list] = {}
        self._lock = threading.Lock()

    # ── L1: 短期记忆 (Session) ──────────────────────────────

    def record_search(self, query: str, results: list[dict] | None = None) -> None:
        """记录一次搜索 (写入 L1 + L2)。"""
        with self._lock:
            self._session_queries.append(query)
            if results is not None:
                self._session_results[query] = results

        # 写入 L2 (持久化)
        self._append_history(query)

    def get_session_history(self, limit: int = 5) -> list[str]:
        """获取当前会话的最近查询。"""
        with self._lock:
            return self._session_queries[-limit:]

    def get_session_results(self, query: str) -> list[dict] | None:
        """获取当前会话中某查询的结果。"""
        with self._lock:
            return self._session_results.get(query)

    def clear_session(self) -> None:
        """清除当前会话记忆。"""
        with self._lock:
            self._session_queries.clear()
            self._session_results.clear()

    # ── L2: 中期记忆 (Search History) ───────────────────────

    def get_history(self, limit: int = 20) -> list[dict]:
        """获取搜索历史。"""
        history = self._load_history()
        return history[:limit]

    def get_popular(self, limit: int = 10) -> list[dict]:
        """获取热门查询。"""
        history = self._load_history()
        queries = [h["query"] for h in history]
        counter = Counter(queries)
        return [{"query": q, "count": c} for q, c in counter.most_common(limit)]

    def get_recent_unique(self, limit: int = 5, hours: int | None = None) -> list[str]:
        """获取最近不重复的查询。"""
        history = self._load_history()
        seen: set[str] = set()
        unique: list[str] = []

        for h in history:
            q = h["query"]
            if q in seen:
                continue

            # 时间过滤
            if hours and h.get("timestamp"):
                try:
                    ts = datetime.fromisoformat(h["timestamp"])
                    if datetime.now() - ts > timedelta(hours=hours):
                        continue
                except (ValueError, TypeError):
                    pass

            seen.add(q)
            unique.append(q)
            if len(unique) >= limit:
                break

        return unique

    def clear_history(self) -> dict:
        """清除搜索历史。"""
        self._save_history([])
        return {"action": "clear", "count": 0}

    def _append_history(self, query: str) -> None:
        """追加一条搜索记录。"""
        history = self._load_history()
        entry = {"query": query, "timestamp": datetime.now().isoformat()}
        # 去重: 移除已有相同 query
        history = [h for h in history if h.get("query") != query]
        history.insert(0, entry)
        # LRU 淘汰
        history = history[: self.max_history]
        self._save_history(history)

    def _load_history(self) -> list[dict]:
        """加载历史记录。"""
        if self.history_path.exists():
            try:
                data = json.loads(self.history_path.read_text())
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_history(self, history: list[dict]) -> None:
        """保存历史记录。"""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2))

    # ── L3: 长期记忆 (Ontology) ─────────────────────────────

    def get_related_entities(self, query: str, limit: int = 5) -> list[dict]:
        """从本体图谱获取相关实体。"""
        from kos.db import get_connection
        from kos.config import get_artifact_path

        try:
            conn = get_connection(get_artifact_path("retrievalDatabase"))
            rows = conn.execute(
                """SELECT entity_id, label, entity_type, description
                   FROM kos_entities
                   WHERE label LIKE ? OR ? LIKE '%' || label || '%'
                   LIMIT ?""",
                (f"%{query}%", query, limit),
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
        except Exception:
            return []

    def get_entity_timeline(self, entity_id: str) -> list[dict]:
        """获取实体时间线 (关联文档按时间排序)。"""
        from kos.db import get_connection
        from kos.config import get_artifact_path

        try:
            conn = get_connection(get_artifact_path("retrievalDatabase"))
            rows = conn.execute(
                """SELECT d.title, d.zone, d.canonical_path, d.created_at, ed.relevance
                   FROM kos_entity_docs ed
                   JOIN documents d ON ed.doc_id = d.doc_id
                   WHERE ed.entity_id = ?
                   ORDER BY d.created_at DESC LIMIT 20""",
                (entity_id,),
            ).fetchall()
            conn.close()
            return [
                {
                    "title": r["title"],
                    "zone": r["zone"],
                    "canonical_path": r["canonical_path"],
                    "created_at": r["created_at"],
                    "relevance": r["relevance"],
                }
                for r in rows
            ]
        except Exception:
            return []

    # ── 三层合并 ────────────────────────────────────────────

    def get_full_context(self, query: str) -> dict[str, Any]:
        """获取三层记忆合并的完整上下文。"""
        return {
            "query": query,
            "l1_session": self.get_session_history(),
            "l2_recent": self.get_recent_unique(limit=5),
            "l2_popular": self.get_popular(limit=5),
            "l3_entities": self.get_related_entities(query),
        }

    def get_stats(self) -> dict[str, Any]:
        """获取记忆统计。"""
        history = self._load_history()
        return {
            "session_queries": len(self._session_queries),
            "total_history": len(history),
            "unique_queries": len(set(h.get("query", "") for h in history)),
            "history_path": str(self.history_path),
        }


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Memory Tier")
    parser.add_argument(
        "action",
        choices=["history", "popular", "stats", "clear", "context"],
        default="history",
        nargs="?",
        help="Action",
    )
    parser.add_argument("--query", help="Query for context action")
    parser.add_argument("--limit", type=int, default=10, help="Limit")
    args = parser.parse_args()

    memory = MemoryTier()

    if args.action == "history":
        result = memory.get_history(limit=args.limit)
    elif args.action == "popular":
        result = memory.get_popular(limit=args.limit)
    elif args.action == "stats":
        result = memory.get_stats()
    elif args.action == "clear":
        result = memory.clear_history()
    elif args.action == "context":
        if not args.query:
            print("Error: --query required for context action")
            return
        result = memory.get_full_context(args.query)
    else:
        result = {"error": f"Unknown action: {args.action}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
