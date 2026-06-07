"""BOS 模块 e2e 测试 (P51)
测试范围: bos_router, bos_metrics, bos_cache, bos_rate_limiter, bos_circuit_breaker
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


class TestBOSRouter:
    def test_register_and_resolve(self):
        from agora.mcp.bos_router import BOSRouter
        r = BOSRouter()
        r.register("bos://memory/kos/", "poc", {"domain": "memory"})
        r.register("bos://memory/kos/search", "poc", {"action": "search"})

        route = r.resolve("bos://memory/kos/search")
        assert route is not None
        assert route["adapter"] == "poc"

    def test_longest_prefix_match(self):
        from agora.mcp.bos_router import BOSRouter
        r = BOSRouter()
        r.register("bos://memory/", "generic")  # shorter
        r.register("bos://memory/kos/", "specific")  # longer

        route = r.resolve("bos://memory/kos/search")
        assert route["adapter"] == "specific"

    def test_idempotent_register(self):
        from agora.mcp.bos_router import BOSRouter
        r = BOSRouter()
        r.register("bos://test/", "poc", {"val": 1})
        r.register("bos://test/", "proxy", {"val": 2})
        assert r.count() == 1
        config = r.resolve("bos://test/action")["config"]
        assert config["val"] == 1  # 第一次注册保留

    def test_resolve_nonexistent(self):
        from agora.mcp.bos_router import BOSRouter
        r = BOSRouter()
        assert r.resolve("bos://nonexistent/path") is None

    def test_stats(self):
        from agora.mcp.bos_router import BOSRouter
        r = BOSRouter()
        r.register("bos://a/", "poc")
        r.register("bos://b/", "proxy")
        r.register("bos://c/", "poc")
        assert r.stats() == {"poc": 2, "proxy": 1}


class TestBOSMetrics:
    def test_record_and_status(self):
        from agora.mcp.bos_metrics import bos_metrics
        bos_metrics.record("bos://memory/kos/search", True, 100)
        bos_metrics.record("bos://memory/kos/search", False, 200)

        status = bos_metrics.status("bos://memory/")
        s = status["bos://memory/kos"]
        assert s["calls"] >= 2
        assert s["failure"] >= 1

    def test_summary(self):
        from agora.mcp.bos_metrics import bos_metrics
        s = bos_metrics.summary()
        assert "total_calls" in s
        assert "success_rate" in s


class TestBOSCache:
    def test_set_get(self):
        from agora.mcp.bos_middleware import Cache
        c = Cache()
        c.set("bos://test", {"q": "hello"}, "world", ttl=999)
        assert c.get("bos://test", {"q": "hello"}) == "world"

    def test_miss(self):
        from agora.mcp.bos_middleware import Cache
        c = Cache()
        assert c.get("bos://nonexistent") is None

    def test_different_params_miss(self):
        from agora.mcp.bos_middleware import Cache
        c = Cache()
        c.set("bos://test", {"q": "hello"}, "world", ttl=999)
        assert c.get("bos://test", {"q": "bye"}) is None

    def test_non_serializable_skip(self):
        from agora.mcp.bos_middleware import Cache
        c = Cache()
        class Bad:
            pass
        c.set("bos://test", {"obj": Bad()}, "value", ttl=999)
        # 不应该崩溃，应该跳过


class TestBOSCircuitBreaker:
    def test_open_after_failures(self):
        from agora.mcp.bos_middleware import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=3600)
        assert not cb.is_open("bos://test")
        cb.record_failure("bos://test")
        assert not cb.is_open("bos://test")
        cb.record_failure("bos://test")
        assert cb.is_open("bos://test")

    def test_recover_after_success(self):
        from agora.mcp.bos_middleware import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=3600)
        cb.record_failure("bos://test")
        cb.record_success("bos://test")
        assert not cb.is_open("bos://test")


class TestBOSRateLimiter:
    def test_acquire_and_limit(self):
        from agora.mcp.bos_middleware import RateLimiter
        rl = RateLimiter(default_qps=2)
        assert rl.acquire("bos://test")
        assert rl.acquire("bos://test")
        assert not rl.acquire("bos://test")  # 超出 QPS

    def test_configure_per_prefix(self):
        from agora.mcp.bos_middleware import RateLimiter
        rl = RateLimiter(default_qps=10)
        rl.configure("bos://slow/", qps=1)
        assert rl.acquire("bos://slow/action")
        assert not rl.acquire("bos://slow/action")


class TestRetryPolicy:
    def test_retry_success(self):
        import asyncio
        from agora.mcp.bos_middleware import retry_policy

        async def _test():
            async def fn():
                return 42
            result, ok = await retry_policy.wrap("bos://test", fn)
            assert result == 42
            assert ok is True

        asyncio.run(_test())

    def test_retry_failure(self):
        import asyncio
        from agora.mcp.bos_middleware import retry_policy

        async def _test():
            async def fn():
                raise RuntimeError("boom")
            result, ok = await retry_policy.wrap("bos://test", fn)
            assert ok is False
            assert isinstance(result, RuntimeError)

        asyncio.run(_test())
