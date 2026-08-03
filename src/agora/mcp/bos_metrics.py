"""BOS 可观测性 — Metrics 统计 (P46 W2)
========================================
按 BOS URI 前缀统计调用量、成功率、延迟。
支持 SQLite 持久化 (重启不丢数据)。

用法:
    from agora.mcp.bos_metrics import bos_metrics

    bos_metrics.record("bos://memory/kos/search", success=True, latency_ms=42)

    @bos_metrics.track("bos://memory/")
    async def my_handler(uri, *args):
        ...
"""

from __future__ import annotations

import functools
import os
import sqlite3
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# ── SQLite 持久化 ─────────────────────────────────────────

_DB_PATH = os.environ.get(
    "AGORA_METRICS_DB",
    str(Path.home() / ".agora" / "bos_metrics.db"),
)


class MetricsStore:
    """SQLite 持久化存储层。"""

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地连接。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self) -> None:
        """初始化表结构。"""
        try:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bos_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prefix TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 1,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    domain TEXT DEFAULT '',
                    package TEXT DEFAULT '',
                    action TEXT DEFAULT '',
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bos_metrics_prefix
                ON bos_metrics(prefix)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bos_metrics_ts
                ON bos_metrics(timestamp)
            """)
            conn.commit()
            self._enabled = True
        except Exception:  # defensive fallback
            self._enabled = False

    def insert(self, prefix: str, uri: str, success: bool, latency_ms: int) -> None:
        """插入一条记录。"""
        if not self._enabled:
            return
        try:
            parts = uri.split("/")
            domain = parts[2] if len(parts) > 2 else ""
            package = parts[3] if len(parts) > 3 else ""
            action = parts[4] if len(parts) > 4 else ""
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO bos_metrics (prefix, uri, success, latency_ms, "
                "domain, package, action, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (
                    prefix,
                    uri,
                    1 if success else 0,
                    latency_ms,
                    domain,
                    package,
                    action,
                    time.time(),
                ),
            )
            conn.commit()
        except Exception:  # defensive fallback
            pass  # 静默 fallback，不影响主流程

    def load_history(self) -> dict[str, dict[str, int]]:
        """从 SQLite 加载历史聚合数据。"""
        stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"calls": 0, "success": 0, "failure": 0, "total_latency_ms": 0}
        )
        if not self._enabled:
            return dict(stats)
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT prefix, success, latency_ms FROM bos_metrics"
            ).fetchall()
            for prefix, success, latency_ms in rows:
                s = stats[prefix]
                s["calls"] += 1
                if success:
                    s["success"] += 1
                else:
                    s["failure"] += 1
                s["total_latency_ms"] += latency_ms
        except Exception:  # defensive fallback
            pass
        return dict(stats)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def db_path(self) -> str:
        return self._db_path


# ── BOSMetrics 类 ──────────────────────────────────────────


class BOSMetrics:
    """BOS 操作指标收集器。

    按 URI 前缀聚合统计，支持分级汇总。
    数据持久化到 SQLite (通过 MetricsStore)。
    """

    def __init__(self):
        self._store = MetricsStore()
        # prefix → {"calls": int, "success": int, "failure": int, "total_latency_ms": int}
        self._stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"calls": 0, "success": 0, "failure": 0, "total_latency_ms": 0}
        )
        # 从 SQLite 加载历史数据
        historical = self._store.load_history()
        for prefix, data in historical.items():
            self._stats[prefix] = data

    def record(self, uri: str, success: bool = True, latency_ms: int = 0) -> None:
        """记录一次调用。"""
        prefix = self._prefix(uri)
        s = self._stats[prefix]
        s["calls"] += 1
        if success:
            s["success"] += 1
        else:
            s["failure"] += 1
        s["total_latency_ms"] += latency_ms
        # 异步写入 SQLite
        self._store.insert(prefix, uri, success, latency_ms)

    def track(self, uri_prefix: str):
        """装饰器：自动记录函数调用的指标。

        用法:
            @bos_metrics.track("bos://memory/")
            async def read_resource(uri, *args):
                ...

        函数必须包含 `uri` 参数（第一个位置参数或关键字参数）。
        """

        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                uri = kwargs.get("uri") or (args[0] if args else "")
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    ms = int((time.time() - start) * 1000)
                    self.record(uri, success=True, latency_ms=ms)
                    return result
                except Exception:  # defensive fallback
                    ms = int((time.time() - start) * 1000)
                    self.record(uri, success=False, latency_ms=ms)
                    raise

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                uri = kwargs.get("uri") or (args[0] if args else "")
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    ms = int((time.time() - start) * 1000)
                    self.record(uri, success=True, latency_ms=ms)
                    return result
                except Exception:  # defensive fallback
                    ms = int((time.time() - start) * 1000)
                    self.record(uri, success=False, latency_ms=ms)
                    raise

            import asyncio

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def status(self, prefix: str = "") -> dict[str, Any]:
        """查询指标状态。

        Args:
            prefix: 过滤前缀 (空则返回所有)
        """
        result = {}
        for p, s in sorted(self._stats.items()):
            if prefix and not p.startswith(prefix):
                continue
            calls = s["calls"]
            avg_latency = s["total_latency_ms"] / calls if calls > 0 else 0
            success_rate = s["success"] / calls if calls > 0 else 0
            result[p] = {
                "calls": calls,
                "success": s["success"],
                "failure": s["failure"],
                "success_rate": round(success_rate, 4),
                "avg_latency_ms": round(avg_latency, 1),
            }
        return result

    def summary(self) -> dict[str, Any]:
        """全量汇总。"""
        total_calls = sum(s["calls"] for s in self._stats.values())
        total_success = sum(s["success"] for s in self._stats.values())
        total_failure = sum(s["failure"] for s in self._stats.values())
        total_latency = sum(s["total_latency_ms"] for s in self._stats.values())
        return {
            "total_calls": total_calls,
            "total_success": total_success,
            "total_failure": total_failure,
            "success_rate": round(total_success / total_calls, 4)
            if total_calls > 0
            else 0,
            "avg_latency_ms": round(total_latency / total_calls, 1)
            if total_calls > 0
            else 0,
            "prefixes": len(self._stats),
            "db_path": self._store.db_path,
            "db_enabled": self._store.enabled,
        }

    def capability_status(self) -> dict[str, Any]:
        """能力粒度使用统计 (B1: 深化 — 按 domain/package/action 全维度)。

        输出:
            { "bos://domain/package/action": {calls, success, failure,
              success_rate, avg_latency_ms, last_used, stale_days} }
        """
        if not self._store.enabled:
            return {"_note": "metrics store disabled", "capabilities": {}}
        try:
            conn = self._store._get_conn()
            rows = conn.execute(
                "SELECT domain, package, action, COUNT(*) as calls, "
                "SUM(success) as ok, SUM(latency_ms) as lat, "
                "MAX(timestamp) as last_ts "
                "FROM bos_metrics GROUP BY domain, package, action"
            ).fetchall()
        except Exception:  # defensive fallback
            return {"capabilities": {}}
        now = time.time()
        caps: dict[str, dict[str, Any]] = {}
        for domain, package, action, calls, ok, lat, last_ts in rows:
            if not action or not package:
                continue
            uri = f"bos://{domain}/{package}/{action}"
            success = ok or 0
            caps[uri] = {
                "calls": calls,
                "success": success,
                "failure": calls - success,
                "success_rate": round(success / calls, 4) if calls > 0 else 0,
                "avg_latency_ms": round((lat or 0) / calls, 1) if calls > 0 else 0,
                "last_used": last_ts or 0,
                "stale_days": round((now - (last_ts or 0)) / 86400, 1),
            }
        return {"capabilities": caps, "count": len(caps)}

    def health(self) -> dict[str, Any]:
        """BOS 可观测性健康检查。"""
        s = self.summary()
        services_ok = 0
        services_degraded = 0
        for data in self.status().values():
            if data["success_rate"] >= 0.95:
                services_ok += 1
            elif data["calls"] > 0:
                services_degraded += 1

        return {
            "status": "ok",
            "metrics_db": self._store.db_path,
            "metrics_persisted": self._store.enabled,
            "total_calls": s["total_calls"],
            "success_rate": s["success_rate"],
            "services_tracked": s["prefixes"],
            "services_healthy": services_ok,
            "services_degraded": services_degraded,
        }

    @staticmethod
    def _prefix(uri: str) -> str:
        """提取统计前缀: bos://domain/package"""
        parts = uri.split("/")
        if len(parts) >= 4:
            return "/".join(parts[:4])
        return uri


# ── 全局单例 ──
bos_metrics = BOSMetrics()
