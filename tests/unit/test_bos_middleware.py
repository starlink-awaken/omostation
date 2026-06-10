"""Unit tests for agora.mcp.bos_middleware — BOS 中间件.

验证:
  1. RateLimiter — 滑动窗口限流、QPS 配置、状态查询
  2. CircuitBreaker — 熔断开关、成功/失败记录、恢复
  3. Cache — TTL 缓存、命中/未命中、失效、状态
  4. RetryPolicy — 重试策略、指数退避、状态
  5. ConfigWatcher — polling 文件监听
"""
from __future__ import annotations

import time
import threading
from pathlib import Path

import pytest

from agora.mcp.bos_middleware import (  # type: ignore[import-not-found]
    RateLimiter,
    CircuitBreaker,
    Cache,
    RetryPolicy,
    ConfigWatcher,
)


# ═══════════════════════════════════════════════════════════════
# RateLimiter
# ═══════════════════════════════════════════════════════════════


class TestRateLimiter:
    def setup_method(self):
        self.limiter = RateLimiter(default_qps=10, window_s=1.0)

    def test_acquire_allows_within_limit(self):
        """窗口内不超过 QPS 应放行。"""
        for _ in range(10):
            assert self.limiter.acquire("bos://test/uri") is True

    def test_acquire_blocks_exceeding_limit(self):
        """超过 QPS 应拒绝。"""
        for _ in range(10):
            self.limiter.acquire("bos://test/uri")
        assert self.limiter.acquire("bos://test/uri") is False

    def test_acquire_window_resets(self):
        """窗口过期后应重置计数。"""
        for _ in range(10):
            self.limiter.acquire("bos://test/uri")
        # 模拟窗口过期
        self.limiter._windows[self.limiter._match_key("bos://test/uri")] = (time.time() - 2, 10)
        # 新窗口应放行
        assert self.limiter.acquire("bos://test/uri") is True

    def test_configure_qps_increases_limit(self):
        """配置更高 QPS 后应放行更多请求。"""
        self.limiter.configure("bos://test/bulk/", qps=50)
        for _ in range(50):
            assert self.limiter.acquire("bos://test/bulk/op1") is True

    def test_configure_qps_uses_longest_prefix(self):
        """最长前缀匹配 QPS 配置。"""
        self.limiter.configure("bos://test/", qps=5)
        self.limiter.configure("bos://test/premium/", qps=50)
        for _ in range(50):
            assert self.limiter.acquire("bos://test/premium/action") is True
        # 非 premium 路径受 bos://test/ 限制
        for _ in range(5):
            self.limiter.acquire("bos://test/normal")
        assert self.limiter.acquire("bos://test/normal") is False

    def test_status_returns_config_and_windows(self):
        """status() 应返回配置的 QPS 和活跃窗口数。"""
        self.limiter.configure("bos://test/", qps=20)
        status = self.limiter.status()
        assert "configured_qps" in status
        assert "active_windows" in status

    def test_status_with_uri(self):
        """传入 URI 应返回该 URI 的窗口状态。"""
        self.limiter.acquire("bos://test/specific")
        status = self.limiter.status("bos://test/specific")
        assert status["uri"] == "bos://test/specific"

    def test_different_uris_independent(self):
        """不同 URI 的限流应独立。"""
        for _ in range(10):
            self.limiter.acquire("bos://alpha")
        assert self.limiter.acquire("bos://beta") is True  # beta 未被限流

    def test_edge_short_uri(self):
        """短 URI 不影响匹配。"""
        assert self.limiter.acquire("bos://x") is True

    def test_edge_empty_uri(self):
        """空 URI 放行（使用默认 QPS）。"""
        assert self.limiter.acquire("") is True


# ═══════════════════════════════════════════════════════════════
# CircuitBreaker
# ═══════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    def setup_method(self):
        self.cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.05)

    def teardown_method(self):
        self.cb.shutdown()

    def test_initial_state_closed(self):
        """初始状态应是 CLOSED。"""
        assert self.cb.is_open("bos://test/svc") is False

    def test_opens_after_failures(self):
        """连续 N 次失败后应 OPEN。"""
        for _ in range(3):
            self.cb.record_failure("bos://test/svc")
        assert self.cb.is_open("bos://test/svc") is True

    def test_success_keeps_closed(self):
        """成功不应打开熔断。"""
        for _ in range(5):
            self.cb.record_success("bos://test/svc")
        assert self.cb.is_open("bos://test/svc") is False

    def test_success_resets_failure_count(self):
        """成功后应重置失败计数。"""
        for _ in range(2):
            self.cb.record_failure("bos://test/svc")
        self.cb.record_success("bos://test/svc")  # 重置
        # 再失败 2 次不应 OPEN（需要连续 3 次）
        for _ in range(2):
            self.cb.record_failure("bos://test/svc")
        assert self.cb.is_open("bos://test/svc") is False
        # 第 3 次才 OPEN
        self.cb.record_failure("bos://test/svc")
        assert self.cb.is_open("bos://test/svc") is True

    def test_half_open_after_recovery_timeout(self):
        """OPEN 后等待 recovery_timeout 应转为 HALF_OPEN (is_open=False)。"""
        for _ in range(3):
            self.cb.record_failure("bos://test/svc")
        assert self.cb.is_open("bos://test/svc") is True
        time.sleep(0.06)  # 等待恢复超时
        # is_open 检查时自动转为 HALF_OPEN
        assert self.cb.is_open("bos://test/svc") is False

    def test_success_after_half_open_closes(self):
        """HALF_OPEN 后成功应恢复为 CLOSED。"""
        for _ in range(3):
            self.cb.record_failure("bos://test/svc")
        time.sleep(0.06)
        self.cb.is_open("bos://test/svc")  # 触发 HALF_OPEN
        self.cb.record_success("bos://test/svc")
        assert self.cb.is_open("bos://test/svc") is False
        # 确认已完全恢复
        self.cb.record_failure("bos://test/svc")
        assert self.cb.is_open("bos://test/svc") is False  # 只失败 1 次

    def test_different_uris_independent(self):
        """不同 URI 的熔断状态独立。"""
        for _ in range(3):
            self.cb.record_failure("bos://svc-a")
        assert self.cb.is_open("bos://svc-a") is True
        assert self.cb.is_open("bos://svc-b") is False

    def test_status_without_uri(self):
        """status() 无 URI 返回所有状态。"""
        self.cb.record_failure("bos://test/svc")
        status = self.cb.status()
        key = self.cb._match_key("bos://test/svc")
        assert key in status

    def test_status_with_uri(self):
        """status() 传入 URI 返回该 URI 的状态。"""
        self.cb.record_failure("bos://test/svc")
        status = self.cb.status("bos://test/svc")
        key = self.cb._match_key("bos://test/svc")
        assert key in status
        assert status[key]["state"] in ("closed", "open")


# ═══════════════════════════════════════════════════════════════
# Cache
# ═══════════════════════════════════════════════════════════════


class TestCache:
    def setup_method(self):
        self.cache = Cache()

    def test_set_and_get(self):
        """写入后应能读取。"""
        self.cache.set("bos://test/uri", {"key": "val"}, "result_data", ttl=30)
        assert self.cache.get("bos://test/uri", {"key": "val"}) == "result_data"

    def test_get_miss(self):
        """未写入应返回 None。"""
        assert self.cache.get("bos://nonexistent") is None

    def test_get_expired(self):
        """过期数据应返回 None。"""
        self.cache.set("bos://test/uri", None, "data", ttl=0)  # ttl=0 立即过期
        time.sleep(0.01)
        assert self.cache.get("bos://test/uri") is None

    def test_different_params_different_keys(self):
        """不同参数应命中不同缓存。"""
        self.cache.set("bos://test/uri", {"q": "a"}, "result_a")
        self.cache.set("bos://test/uri", {"q": "b"}, "result_b")
        assert self.cache.get("bos://test/uri", {"q": "a"}) == "result_a"
        assert self.cache.get("bos://test/uri", {"q": "b"}) == "result_b"

    def test_invalidate(self):
        """失效应清除匹配的缓存（含不同参数组合）。"""
        self.cache.set("bos://test/uri", {"x": 1}, "data_a")
        self.cache.set("bos://test/uri", {"x": 2}, "data_b")
        self.cache.set("bos://other/uri", None, "should_survive")
        self.cache.invalidate("bos://test/uri")
        # 同一 URI 的不同参数组合应全部失效
        assert self.cache.get("bos://test/uri", {"x": 1}) is None
        assert self.cache.get("bos://test/uri", {"x": 2}) is None
        # 其他 URI 应保留
        assert self.cache.get("bos://other/uri") == "should_survive"

    def test_status_counts(self):
        """status() 应统计活跃/过期条目。"""
        self.cache.set("bos://fresh", None, "data", ttl=30)
        self.cache.set("bos://stale", None, "data", ttl=0)
        status = self.cache.status()
        assert status["active_entries"] == 1  # fresh
        assert status["total"] == 2

    def test_no_params_get(self):
        """无参数查询应正确。"""
        self.cache.set("bos://test/uri", None, "no_params")
        assert self.cache.get("bos://test/uri") == "no_params"

    def test_unserializable_params_fall_back(self):
        """不可序列化的参数不应报错，返回 None。"""
        class Unserializable:
            pass
        result = self.cache.get("bos://test/uri", {"bad": Unserializable()})
        assert result is None


# ═══════════════════════════════════════════════════════════════
# RetryPolicy
# ═══════════════════════════════════════════════════════════════


class TestRetryPolicy:
    def setup_method(self):
        self.rp = RetryPolicy(max_retries=2, base_delay=0.01)

    async def test_wrap_success_first_try(self):
        """一次成功不应重试。"""
        async def ok_func(*a, **kw):
            return ("success_result", True)

        result, ok = await self.rp.wrap("bos://test/uri", ok_func)
        assert ok is True
        assert result == ("success_result", True)

    async def test_wrap_retries_on_failure(self):
        """失败应重试。"""
        attempt_count = [0]

        async def fail_then_ok(*a, **kw):
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise RuntimeError(f"attempt {attempt_count[0]} failed")
            return ("recovered", True)

        result, ok = await self.rp.wrap("bos://test/uri", fail_then_ok)
        assert ok is True
        assert result == ("recovered", True)

    async def test_wrap_exhaust_retries(self):
        """超过最大重试次数应返回失败。"""
        async def always_fail(*a, **kw):
            raise RuntimeError("always fails")

        result, ok = await self.rp.wrap("bos://test/uri", always_fail)
        assert ok is False
        assert isinstance(result, RuntimeError)

    def test_status_without_uri(self):
        assert "active_retries" in self.rp.status()

    def test_edge_no_retries(self):
        """max_retries=0 不重试。"""
        rp = RetryPolicy(max_retries=0)
        assert rp.max_retries == 0


# ═══════════════════════════════════════════════════════════════
# ConfigWatcher
# ═══════════════════════════════════════════════════════════════


class TestConfigWatcher:
    def test_start_stop(self, tmp_path: Path):
        """start/stop 不报错。"""
        cfg = tmp_path / "test-config.yaml"
        cfg.write_text("key: value\n")
        watcher = ConfigWatcher(str(cfg))
        watcher.start(interval=0.1)
        assert watcher._running is True
        assert watcher._thread is not None
        watcher.stop()
        assert watcher._running is False

    def test_detect_file_change(self, tmp_path: Path):
        """文件变化应触发 on_change 回调。"""
        cfg = tmp_path / "watch-config.yaml"
        cfg.write_text("v1\n")
        changed = [False]

        def on_change():
            changed[0] = True

        watcher = ConfigWatcher(str(cfg), on_change=on_change)
        watcher.start(interval=0.05)
        time.sleep(0.06)
        cfg.write_text("v2\n")  # 写新内容，mtime 变化
        time.sleep(0.1)
        watcher.stop()
        assert changed[0] is True

    def test_no_file_no_crash(self):
        """配置文件不存在时不报错。"""
        watcher = ConfigWatcher("/tmp/nonexistent-file-12345.yaml")
        watcher.start(interval=0.05)
        time.sleep(0.06)
        watcher.stop()  # should not raise

    def test_on_change_not_called_without_change(self, tmp_path: Path):
        """文件不变时不触发回调。"""
        cfg = tmp_path / "static.yaml"
        cfg.write_text("static\n")
        called = [0]

        def on_change():
            called[0] += 1

        watcher = ConfigWatcher(str(cfg), on_change=on_change)
        watcher.start(interval=0.05)
        time.sleep(0.12)
        watcher.stop()
        assert called[0] == 0  # 文件没变

    def test_stop_stops_thread(self):
        """stop 后线程应退出。"""
        watcher = ConfigWatcher("/tmp/nonexistent.yaml")
        watcher.start(interval=0.05)
        watcher.stop()
        assert watcher._running is False
        watcher._thread.join(timeout=2)
        assert not watcher._thread.is_alive()
