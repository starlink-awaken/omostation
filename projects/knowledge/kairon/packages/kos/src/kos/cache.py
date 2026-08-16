#!/usr/bin/env python3
# ruff: noqa
"""
KOS Cache — 三级缓存管理器

实现分层缓存架构:
  L1: 内存 LRU 缓存 (容量 1000, TTL 5min, <0.1ms)
  L2: SQLite FTS5 索引 (<10ms)
  L3: LanceDB 向量 + 图谱遍历 (<100ms)

Usage:
    from kos.cache import SearchCache

    cache = SearchCache()

    # 获取缓存结果
    result = cache.get("query", mode="hybrid")

    # 设置缓存
    cache.set("query", mode="hybrid", results=[...])

    # 获取统计
    stats = cache.stats()
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class CacheEntry:
    """缓存条目。"""

    key: str
    data: Any
    created_at: float
    ttl: float  # seconds
    hits: int = 0

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        self.hits += 1


class LRUCache:
    """线程安全的 LRU 缓存。"""

    def __init__(self, capacity: int = 1000, default_ttl: float = 300.0):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.expired:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            return entry.data

    def set(self, key: str, data: Any, ttl: float | None = None) -> None:
        with self._lock:
            if key in self._cache:
                # Update existing
                self._cache.move_to_end(key)
                self._cache[key].data = data
                self._cache[key].created_at = time.time()
            else:
                # Evict oldest if at capacity
                if len(self._cache) >= self.capacity:
                    self._cache.popitem(last=False)
                self._cache[key] = CacheEntry(
                    key=key,
                    data=data,
                    created_at=time.time(),
                    ttl=ttl or self.default_ttl,
                )

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._cache),
                "capacity": self.capacity,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / max(self._hits + self._misses, 1) * 100, 1),
            }


class SearchCache:
    """搜索三级缓存管理器。

    L1: 内存 LRU (热缓存, TTL 5min)
    L2: SQLite 持久化缓存 (温缓存, TTL 1hour)
    L3: 实际检索 (冷检索)
    """

    def __init__(
        self,
        l1_capacity: int = 1000,
        l1_ttl: float = 300.0,
        l2_ttl: float = 3600.0,
        db_path: str | None = None,
    ):
        from kos.config import get_artifact_path

        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self.l1 = LRUCache(capacity=l1_capacity, default_ttl=l1_ttl)
        self.l2_ttl = l2_ttl
        self._enable_l2 = True  # 是否启用 L2 缓存

    # ── 核心 API ────────────────────────────────────────────

    def get(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 10,
    ) -> dict[str, Any] | None:
        """获取缓存结果。

        按 L1 → L2 顺序查找。

        Returns:
            缓存命中返回结果，否则返回 None。
        """
        cache_key = self._make_key(query, mode, limit)

        # L1: 内存缓存
        result = self.l1.get(cache_key)
        if result is not None:
            result["cache_hit"] = "L1"
            return self._restore_result(result)

        # L2: SQLite 持久化缓存
        if self._enable_l2:
            result = self._l2_get(cache_key)
            if result is not None:
                # 提升 to L1
                self.l1.set(cache_key, result)
                result["cache_hit"] = "L2"
                return self._restore_result(result)

        return None

    @staticmethod
    def _restore_result(cached: dict) -> dict:
        """从缓存条目重建完整的搜索结果结构。"""
        return {
            "query": cached.get("query", ""),
            "mode": cached.get("mode", "hybrid"),
            "results": cached.get("results", []),
            "count": cached.get("count", len(cached.get("results", []))),
            "query_plan": cached.get("query_plan", {}),
            "sources": cached.get("metadata", {}).get("sources", {}),
            "elapsed_ms": cached.get("elapsed_ms", 0),
            "cache_hit": cached.get("cache_hit"),
        }

    def set(
        self,
        query: str,
        mode: str,
        results: list[dict],
        limit: int = 10,
        metadata: dict | None = None,
    ) -> None:
        """设置缓存。"""
        cache_key = self._make_key(query, mode, limit)

        entry = {
            "query": query,
            "mode": mode,
            "limit": limit,
            "results": results,
            "metadata": metadata or {},
            "cached_at": datetime.now().isoformat(),
            "cache_hit": None,
        }

        # L1: 内存缓存
        self.l1.set(cache_key, entry)

        # L2: SQLite 持久化缓存
        if self._enable_l2:
            self._l2_set(cache_key, entry)

    def search_with_cache(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 10,
        search_fn=None,
    ) -> dict[str, Any]:
        """带缓存的搜索。

        先查缓存，未命中时调用 search_fn 执行实际检索。

        Args:
            query: 搜索查询。
            mode: 检索模式。
            limit: 最大结果数。
            search_fn: 实际检索函数 (query, mode, limit) -> result。

        Returns:
            搜索结果。
        """
        # 查缓存
        cached = self.get(query, mode, limit)
        if cached is not None:
            return cached

        # 缓存未命中: 执行实际检索
        if search_fn is None:
            from kos.hybrid_search import HybridSearchEngine

            engine = HybridSearchEngine(self.db_path)
            result = engine.search(query, mode=mode, limit=limit, context={"mode": "balanced"})
            engine.close()
        else:
            result = search_fn(query, mode, limit)

        # 写入缓存 (只缓存有结果的查询)
        if result.get("results"):
            self.set(
                query,
                mode,
                result.get("results", []),
                limit,
                {
                    "sources": result.get("sources", {}),
                    "elapsed_ms": result.get("elapsed_ms", 0),
                },
            )
            result["cache_hit"] = None  # 未命中
        else:
            result["cache_hit"] = None

        return result

    def invalidate(self, query: str, mode: str = "hybrid", limit: int = 10) -> None:
        """使特定查询的缓存失效。"""
        cache_key = self._make_key(query, mode, limit)
        self.l1.invalidate(cache_key)
        self._l2_delete(cache_key)

    def clear_all(self) -> None:
        """清除所有缓存。"""
        self.l1.clear()
        self._l2_clear()

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计。"""
        l1_stats = self.l1.stats
        l2_size = self._l2_size()

        return {
            "l1_memory": l1_stats,
            "l2_persistent": {
                "size": l2_size,
                "ttl_seconds": self.l2_ttl,
            },
            "total_cache_entries": l1_stats["size"] + l2_size,
        }

    # ── L2 SQLite 缓存 ──────────────────────────────────────

    def _l2_get(self, key: str) -> dict | None:
        """从 L2 获取缓存。"""
        import sqlite3

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT data, created_at FROM search_cache WHERE key=?",
                (key,),
            ).fetchone()
            conn.close()

            if row is None:
                return None

            # Check TTL
            try:
                created = datetime.fromisoformat(row["created_at"])
                if datetime.now() - created > timedelta(seconds=self.l2_ttl):
                    self._l2_delete(key)
                    return None
            except (ValueError, TypeError):
                pass

            return json.loads(row["data"])
        except sqlite3.Error:
            return None

    def _l2_set(self, key: str, entry: dict) -> None:
        """写入 L2 缓存。"""
        import sqlite3

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "INSERT OR REPLACE INTO search_cache (key, data, created_at) VALUES (?,?,?)",
                (key, json.dumps(entry, ensure_ascii=False), datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass

    def _l2_delete(self, key: str) -> None:
        """删除 L2 缓存条目。"""
        import sqlite3

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM search_cache WHERE key=?", (key,))
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass

    def _l2_clear(self) -> None:
        """清除 L2 缓存。"""
        import sqlite3

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DROP TABLE IF EXISTS search_cache")
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass

    def _l2_size(self) -> int:
        """获取 L2 缓存大小。"""
        import sqlite3

        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT COUNT(*) FROM search_cache").fetchone()
            conn.close()
            return row[0] if row else 0
        except sqlite3.Error:
            return 0

    # ── 辅助方法 ────────────────────────────────────────────

    @staticmethod
    def _make_key(query: str, mode: str, limit: int) -> str:
        """生成缓存 key。"""
        raw = f"{query.lower().strip()}:{mode}:{limit}"
        return hashlib.md5(raw.encode()).hexdigest()


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Cache Manager")
    parser.add_argument(
        "action",
        choices=["stats", "clear", "benchmark"],
        default="stats",
        nargs="?",
        help="Action: stats/clear/benchmark",
    )
    args = parser.parse_args()

    cache = SearchCache()

    if args.action == "stats":
        print(json.dumps(cache.get_stats(), ensure_ascii=False, indent=2))
    elif args.action == "clear":
        cache.clear_all()
        print(json.dumps({"status": "cleared"}))
    elif args.action == "benchmark":
        # Simple benchmark
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()

        queries = ["测试", "数字化", "平台", "数据治理", "项目"]
        results = {"with_cache": [], "without_cache": []}

        # Without cache
        t0 = time.time()
        for q in queries:
            engine.search(q, mode="keyword", limit=5)
        results["without_cache_ms"] = round((time.time() - t0) * 1000, 2)  # type: ignore[reportArgumentType]

        # With cache (first run populates)
        t0 = time.time()
        for q in queries:
            cache.search_with_cache(q, mode="keyword", limit=5)
        results["with_cache_first_ms"] = round((time.time() - t0) * 1000, 2)  # type: ignore[reportArgumentType]

        # With cache (second run hits cache)
        t0 = time.time()
        for q in queries:
            cache.search_with_cache(q, mode="keyword", limit=5)
        results["with_cache_second_ms"] = round((time.time() - t0) * 1000, 2)  # type: ignore[reportArgumentType]

        engine.close()
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
