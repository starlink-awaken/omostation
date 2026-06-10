"""Unit tests for agora.mcp.bos_metrics — BOS 可观测性.

验证:
  1. record — 记录调用结果
  2. track — 装饰器自动记录
  3. status — 按前缀查询
  4. summary — 全量汇总
  5. _prefix — URI 前缀提取
"""
from __future__ import annotations

import time

import pytest

from agora.mcp.bos_metrics import BOSMetrics  # type: ignore[import-not-found]


class TestBOSMetricsRecord:
    def setup_method(self):
        self.m = BOSMetrics()

    def test_record_success(self):
        """记录成功调用。"""
        self.m.record("bos://memory/kos/search", success=True, latency_ms=42)
        stats = self.m.status("bos://memory/kos")
        prefix = "bos://memory/kos"
        s = stats.get(prefix)
        assert s is not None
        assert s["calls"] == 1
        assert s["success"] == 1
        assert s["failure"] == 0
        assert s["avg_latency_ms"] == 42.0

    def test_record_failure(self):
        """记录失败调用。"""
        self.m.record("bos://memory/kos/search", success=False, latency_ms=100)
        stats = self.m.status("bos://memory/kos")
        s = stats.get("bos://memory/kos")
        assert s["failure"] == 1
        assert s["success"] == 0

    def test_record_multiple_calls(self):
        """多次调用应累加。"""
        for _ in range(5):
            self.m.record("bos://test/svc", success=True, latency_ms=10)
        stats = self.m.status("bos://test")
        s = stats.get("bos://test/svc")
        assert s is not None
        assert s["calls"] == 5
        assert s["success"] == 5
        assert s["avg_latency_ms"] == 10.0

    def test_record_mixed_success_failure(self):
        """混合成功/失败。"""
        for _ in range(3):
            self.m.record("bos://test/svc", success=True, latency_ms=10)
        for _ in range(2):
            self.m.record("bos://test/svc", success=False, latency_ms=50)
        stats = self.m.status("bos://test")
        s = stats.get("bos://test/svc")
        assert s is not None
        assert s["calls"] == 5
        assert s["success"] == 3
        assert s["failure"] == 2
        # avg = (3*10 + 2*50) / 5 = 26
        assert s["avg_latency_ms"] == 26.0
        # success_rate = 3/5 = 0.6
        assert s["success_rate"] == 0.6

    def test_record_different_prefixes(self):
        """不同 URI 前缀独立统计。"""
        self.m.record("bos://memory/kos/search", success=True)
        self.m.record("bos://analysis/minerva/research", success=True)
        stats = self.m.status()
        assert "bos://memory/kos" in stats
        assert "bos://analysis/minerva" in stats

    def test_record_latency_aggregates(self):
        """延迟应聚合为平均值。"""
        self.m.record("bos://test", success=True, latency_ms=10)
        self.m.record("bos://test", success=True, latency_ms=30)
        stats = self.m.status("bos://test")
        s = stats.get("bos://test")
        assert s["avg_latency_ms"] == 20.0


class TestBOSMetricsTrack:
    def setup_method(self):
        self.m = BOSMetrics()

    def test_track_decorator_async_success(self):
        """track 装饰器应自动记录成功调用。"""

        @self.m.track("bos://test/")
        async def handler(uri: str, **kwargs):
            return "ok"

        import asyncio
        result = asyncio.run(handler("bos://test/svc", key="val"))
        assert result == "ok"
        stats = self.m.status("bos://test")
        assert stats.get("bos://test/svc") is not None
        assert stats["bos://test/svc"]["calls"] == 1
        assert stats["bos://test/svc"]["success"] == 1

    def test_track_decorator_async_failure(self):
        """track 装饰器应自动记录失败调用。"""

        @self.m.track("bos://test/")
        async def failing_handler(uri: str, **kwargs):
            raise ValueError("fail")

        import asyncio
        with pytest.raises(ValueError):
            asyncio.run(failing_handler("bos://test/svc"))
        stats = self.m.status("bos://test")
        assert stats["bos://test/svc"]["calls"] == 1
        assert stats["bos://test/svc"]["failure"] == 1

    def test_track_decorator_sync(self):
        """track 装饰器也支持同步函数。"""

        @self.m.track("bos://test/")
        def sync_handler(uri: str):
            return "sync_ok"

        result = sync_handler("bos://test/sync")
        assert result == "sync_ok"
        stats = self.m.status("bos://test")
        assert stats["bos://test/sync"]["calls"] == 1

    def test_track_decorator_sync_failure(self):
        """同步函数失败也应记录。"""

        @self.m.track("bos://test/")
        def failing_sync(uri: str):
            raise RuntimeError("sync fail")

        with pytest.raises(RuntimeError):
            failing_sync("bos://test/sync")
        stats = self.m.status("bos://test")
        assert stats["bos://test/sync"]["failure"] == 1


class TestBOSMetricsStatus:
    def setup_method(self):
        self.m = BOSMetrics()

    def test_status_all(self):
        """status() 无过滤返回所有。"""
        self.m.record("bos://a/x", success=True)
        self.m.record("bos://b/y", success=True)
        all_stats = self.m.status()
        assert len(all_stats) == 2

    def test_status_filtered(self):
        """status(prefix) 应过滤。"""
        self.m.record("bos://memory/kos/search", success=True)
        self.m.record("bos://analysis/minerva/research", success=True)
        filtered = self.m.status(prefix="bos://memory/")
        assert len(filtered) == 1
        assert "bos://memory/kos" in filtered

    def test_status_empty(self):
        """无数据时 status() 返回空。"""
        assert self.m.status() == {}

    def test_status_no_match(self):
        """不匹配的前缀返回空。"""
        assert self.m.status(prefix="bos://nonexistent/") == {}


class TestBOSMetricsSummary:
    def setup_method(self):
        self.m = BOSMetrics()

    def test_summary_empty(self):
        """无数据时汇总为 0。"""
        s = self.m.summary()
        assert s["total_calls"] == 0
        assert s["total_success"] == 0
        assert s["total_failure"] == 0
        assert s["prefixes"] == 0

    def test_summary_aggregates(self):
        """汇总应正确聚合。"""
        self.m.record("bos://a/x", success=True)
        self.m.record("bos://a/x", success=False)
        self.m.record("bos://b/y", success=True)
        s = self.m.summary()
        assert s["total_calls"] == 3
        assert s["total_success"] == 2
        assert s["total_failure"] == 1
        assert s["prefixes"] == 2
        import pytest as _pt
        assert s["success_rate"] == _pt.approx(2 / 3, rel=1e-2)

    def test_summary_avg_latency(self):
        """汇总平均延迟。"""
        self.m.record("bos://test", success=True, latency_ms=10)
        self.m.record("bos://test", success=True, latency_ms=30)
        s = self.m.summary()
        assert s["avg_latency_ms"] == 20.0


class TestBOSMetricsPrefix:
    def test_prefix_standard(self):
        """标准 URI 应提取 bos://domain/package。"""
        assert BOSMetrics._prefix("bos://memory/kos/search") == "bos://memory/kos"

    def test_prefix_short(self):
        """短 URI 应原样返回。"""
        assert BOSMetrics._prefix("bos://short") == "bos://short"

    def test_prefix_shallow(self):
        """只有 bos://domain 时原样返回。"""
        assert BOSMetrics._prefix("bos://domain") == "bos://domain"
