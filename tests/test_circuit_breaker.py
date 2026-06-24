"""Circuit Breaker — 后端熔断器单元测试"""

from __future__ import annotations

import time

from ecos.workflow import circuit_breaker as cb


def setup_function() -> None:
    cb.reset_all()


def teardown_function() -> None:
    cb.reset_all()


def test_initial_available() -> None:
    """初始状态：所有后端视为可用"""
    assert cb.is_available("test-backend") is True


def test_trip_and_block() -> None:
    """熔断触发后不可用"""
    cb.trip("test-backend", "target-a")
    assert cb.is_available("test-backend", "target-a") is False


def test_different_targets_independent() -> None:
    """不同目标的熔断独立"""
    cb.trip("test-backend", "target-a")
    assert cb.is_available("test-backend", "target-a") is False
    assert cb.is_available("test-backend", "target-b") is True


def test_different_backends_independent() -> None:
    """不同后端的熔断独立"""
    cb.trip("swarm", "agora-mcp")
    assert cb.is_available("swarm", "agora-mcp") is False
    assert cb.is_available("agora", "mcp-gateway") is True


def test_ttl_expiry() -> None:
    """TTL 过期后自动恢复"""
    cb.trip("test-backend", "target", ttl=1)
    assert cb.is_available("test-backend", "target") is False
    time.sleep(1.1)
    assert cb.is_available("test-backend", "target") is True


def test_reset() -> None:
    """手动重置恢复"""
    cb.trip("test-backend", "target")
    assert cb.is_available("test-backend", "target") is False
    cb.reset("test-backend")
    assert cb.is_available("test-backend", "target") is True


def test_reset_all() -> None:
    """全量重置"""
    cb.trip("bk1", "t1")
    cb.trip("bk2", "t2")
    assert cb.reset_all() == 2
    assert cb.is_available("bk1", "t1") is True
    assert cb.is_available("bk2", "t2") is True


def test_status_output() -> None:
    """status() 返回正确格式"""
    cb.trip("test-backend", "target-a")
    cb.trip("test-backend", "target-b")
    s = cb.status()
    assert s["total_tripped"] == 2
    assert len(s["circuits"]) == 2
    for c in s["circuits"]:
        assert "key" in c
        assert "remaining_s" in c
        assert c["remaining_s"] >= 0
