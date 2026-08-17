"""QueryCache 真实现验证 (TASK-1E562797 stub 后端接真).

QueryCache: get/set/invalidate + TTL + get_stats(统计) + generate_cache_key(hash) + hit/miss.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import time

from eidos.query_cache import QueryCache


def test_get_set_roundtrip() -> None:
    c = QueryCache(ttl=10)
    c.set("k", {"v": 1})
    assert c.get("k") == {"v": 1}


def test_ttl_expiry() -> None:
    c = QueryCache(ttl=0.01)
    c.set("k", "v")
    time.sleep(0.02)
    assert c.get("k") is None


def test_hit_miss_stats() -> None:
    c = QueryCache(ttl=10)
    c.get("miss")
    c.set("k", "v")
    c.get("k")
    stats = c.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1
    assert stats["ttl"] == 10


def test_generate_cache_key_stable_and_distinct() -> None:
    c = QueryCache()
    k1 = c.generate_cache_key("a", "b", x=1, y=2)
    k2 = c.generate_cache_key("a", "b", y=2, x=1)
    assert k1 == k2
    k3 = c.generate_cache_key("a", "c")
    assert k1 != k3


def test_invalidate_returns_count() -> None:
    c = QueryCache(ttl=10)
    c.set("k1", 1)
    c.set("k2", 2)
    removed = c.invalidate("k1")
    assert removed == 1
    assert c.get("k1") is None
    assert c.get("k2") == 2


def test_clear() -> None:
    c = QueryCache(ttl=10)
    c.set("k", "v")
    c.clear()
    assert c.get("k") is None


def test_ping() -> None:
    assert QueryCache().ping() is True
