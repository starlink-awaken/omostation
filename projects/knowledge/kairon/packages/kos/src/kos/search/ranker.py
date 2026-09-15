#!/usr/bin/env python3
# ruff: noqa
"""
KOS Search Ranker — 学习型排序.

收集用户反馈, 动态调整排序权重, A/B 测试.

Usage:
    from kos.search.ranker import SearchRanker

    ranker = SearchRanker()
    ranker.log_feedback(query, doc_id, action)
    ranker.get_weight_stats()
"""

import sqlite3
from __future__ import annotations  # type: ignore[reportGeneralTypeIssues]

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class SearchRanker:
    """学习型排序器。"""

    FEEDBACK_DB_PATH = Path.home() / ".kos" / "search_feedback.sqlite"

    def __init__(self):
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.FEEDBACK_DB_PATH))
            self._conn.row_factory = sqlite3.Row
            self._ensure_tables()
        return self._conn

    def _ensure_tables(self):
        """确保反馈表存在。"""
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                mode TEXT,
                results_count INTEGER,
                elapsed_ms REAL,
                timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_query ON user_feedback(query);
            CREATE INDEX IF NOT EXISTS idx_feedback_doc ON user_feedback(doc_id);
        """)

    def log_search(self, query: str, mode: str, results_count: int, elapsed_ms: float):
        """记录搜索查询。"""
        self.conn.execute(
            "INSERT INTO search_queries (query, mode, results_count, elapsed_ms, timestamp) VALUES (?,?,?,?,?)",
            (query, mode, results_count, elapsed_ms, datetime.now().isoformat()),
        )
        self.conn.commit()

    def log_feedback(self, query: str, doc_id: str, action: str):
        """记录用户反馈 (click/dismiss/save)。"""
        self.conn.execute(
            "INSERT INTO user_feedback (query, doc_id, action, timestamp) VALUES (?,?,?,?)",
            (query, doc_id, action, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_weight_stats(self) -> dict[str, Any]:
        """获取排序权重统计。"""
        total_queries = self.conn.execute("SELECT COUNT(*) FROM search_queries").fetchone()[0]
        total_feedback = self.conn.execute("SELECT COUNT(*) FROM user_feedback").fetchone()[0]

        # Top queries
        top_queries = self.conn.execute("""
            SELECT query, COUNT(*) as cnt FROM search_queries
            GROUP BY query ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Popular docs (most clicked)
        popular_docs = self.conn.execute("""
            SELECT doc_id, COUNT(*) as clicks FROM user_feedback
            WHERE action = 'click' GROUP BY doc_id ORDER BY clicks DESC LIMIT 10
        """).fetchall()

        return {
            "total_queries": total_queries,
            "total_feedback": total_feedback,
            "top_queries": [{"query": r["query"], "count": r["cnt"]} for r in top_queries],
            "popular_docs": [{"doc_id": r["doc_id"], "clicks": r["clicks"]} for r in popular_docs],
        }

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


if __name__ == "__main__":
    ranker = SearchRanker()
    stats = ranker.get_weight_stats()
    print(f"Queries: {stats['total_queries']}, Feedback: {stats['total_feedback']}")
    ranker.close()
