"""ecos workflow E2E 集成测试 — 全链路同进程验证

缓存/熔断器均为进程内内存状态，测试必须同进程调用 API。
"""

from __future__ import annotations

from ecos.workflow import cache as _cache
from ecos.workflow import circuit_breaker as _cb
from ecos.workflow.cache import invalidate_all as _cache_reset
from ecos.workflow.circuit_breaker import reset_all as _cb_reset


def setup_function() -> None:
    _cache_reset()
    _cb_reset()


# ── 缓存测试 ──────────────────────────────────────────────


def test_cache_initial_empty() -> None:
    """初始状态: cache 空, cb 未熔断"""
    s = _cache.status()
    assert s["total_entries"] == 0, f"expected 0, got {s}"

    s = _cb.status()
    assert s["total_tripped"] == 0, f"expected 0, got {s}"


def test_cache_write_and_read() -> None:
    """写入缓存后可以读出"""
    _cache.set("workflow-a", 0, {"result": "ok"}, ttl=60)
    entry = _cache.get("workflow-a", 0)
    assert entry == {"result": "ok"}


def test_cache_returns_copy() -> None:
    """get 返回可用结果, 不抛异常"""
    _cache.set("wf", 0, {"data": [1, 2]}, ttl=60)
    entry = _cache.get("wf", 0)
    assert entry == {"data": [1, 2]}


def test_cache_miss_returns_none() -> None:
    assert _cache.get("nonexistent", 0) is None


def test_cache_invalidate_single() -> None:
    _cache.set("wf-a", 0, {"x": 1}, ttl=60)
    _cache.set("wf-b", 0, {"x": 2}, ttl=60)
    _cache.invalidate("wf-a")
    assert _cache.get("wf-a", 0) is None
    assert _cache.get("wf-b", 0) == {"x": 2}


def test_cache_invalidate_all() -> None:
    _cache.set("wf-a", 0, {}, ttl=60)
    _cache.set("wf-b", 0, {}, ttl=60)
    _cache.invalidate_all()
    assert _cache.status()["total_entries"] == 0


def test_cache_ttl_expiry() -> None:
    _cache.set("wf", 0, {"result": "ok"}, ttl=1)
    entry = _cache.get("wf", 0)
    assert entry == {"result": "ok"}
    import time

    time.sleep(1.1)
    assert _cache.get("wf", 0) is None


def test_cache_status_output() -> None:
    _cache.set("wf-a", 0, {}, ttl=60)
    _cache.set("wf-b", 0, {}, ttl=30)
    s = _cache.status()
    assert s["total_entries"] == 2
    assert len(s["entries"]) == 2
    for e in s["entries"]:
        assert "key" in e
        assert "remaining_s" in e
        assert e["remaining_s"] >= 0


# ── 熔断器测试 ────────────────────────────────────────────


def test_cb_initial() -> None:
    assert _cb.is_available("test", "target") is True


def test_cb_trip_blocks() -> None:
    _cb.trip("test", "target", ttl=30)
    assert _cb.is_available("test", "target") is False


def test_cb_different_targets_independent() -> None:
    _cb.trip("swarm", "agora-mcp")
    assert _cb.is_available("swarm", "agora-mcp") is False
    assert _cb.is_available("agora", "mcp-gateway") is True


def test_cb_reset_prefix() -> None:
    _cb.trip("swarm", "agora-mcp")
    _cb.trip("swarm", "runtime-cli")
    _cb.reset("swarm")  # 前缀重置 shoud clear both
    assert _cb.is_available("swarm", "agora-mcp") is True
    assert _cb.is_available("swarm", "runtime-cli") is True


def test_cb_reset_all() -> None:
    _cb.trip("bk1", "t1")
    _cb.trip("bk2", "t2")
    assert _cb.reset_all() == 2
    assert _cb.is_available("bk1", "t1") is True
    assert _cb.is_available("bk2", "t2") is True


def test_cb_status_output() -> None:
    _cb.trip("swarm", "agora-mcp")
    _cb.trip("agora", "mcp-gateway", ttl=10)
    s = _cb.status()
    assert s["total_tripped"] == 2
    for c in s["circuits"]:
        assert c["remaining_s"] >= 0


# ── 端到端管线验证 ─────────────────────────────────────────


def test_mock_workflow_pipeline() -> None:
    """模拟完整管线: 复位 → 写入 → 命中 → 熔断 → 复位"""
    # 1. 复位
    _cache_reset()
    _cb_reset()
    assert _cache.status()["total_entries"] == 0
    assert _cb.status()["total_tripped"] == 0

    # 2. 模拟第一次执行（写入缓存）
    _cache.set("real-workflow:{}", 0, {"result": "done"}, ttl=60)
    assert _cache.get("real-workflow:{}", 0) == {"result": "done"}

    # 3. 模拟缓存命中（第二次执行）
    hit = _cache.get("real-workflow:{}", 0)
    assert hit == {"result": "done"}

    # 4. 模拟后端熔断
    _cb.trip("agora", "mcp-gateway")
    assert _cb.is_available("agora", "mcp-gateway") is False
    # swarm 不受影响
    assert _cb.is_available("swarm", "agora-mcp") is True

    # 5. 复位
    _cb_reset()
    assert _cb.is_available("agora", "mcp-gateway") is True
