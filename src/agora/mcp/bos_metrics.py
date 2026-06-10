"""BOS 可观测性 — Metrics 统计 (P46 W2)
========================================
按 BOS URI 前缀统计调用量、成功率、延迟。

用法:
    from agora.mcp.bos_metrics import bos_metrics

    bos_metrics.record("bos://memory/kos/search", success=True, latency_ms=42)

    @bos_metrics.track("bos://memory/")
    async def my_handler(uri, *args):
        ...
"""

from __future__ import annotations

import time
import functools
from collections import defaultdict
from typing import Any


class BOSMetrics:
    """BOS 操作指标收集器。

    按 URI 前缀聚合统计，支持分级汇总。
    """

    def __init__(self):
        # prefix → {"calls": int, "success": int, "failure": int, "total_latency_ms": int}
        self._stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"calls": 0, "success": 0, "failure": 0, "total_latency_ms": 0}
        )

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
                except Exception:
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
                except Exception:
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
