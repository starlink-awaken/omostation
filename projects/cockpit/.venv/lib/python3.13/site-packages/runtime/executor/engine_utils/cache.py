"""LRU (Least Recently Used) cache with optional TTL support.

Migrated from agentmesh dsl/lru-cache.ts.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache[K, V]:
    """Least Recently Used cache evicting the oldest accessed entry when full."""

    def __init__(self, max_size: int = 100) -> None:
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        self._max_size = max_size
        self._cache: OrderedDict[K, V] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: K) -> V | None:
        value = self._cache.get(key)
        if value is None:
            self._misses += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: K, value: V) -> None:
        if key in self._cache:
            self._cache.pop(key)
        self._cache[key] = value
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
            self._evictions += 1

    def has(self, key: K) -> bool:
        return key in self._cache

    def delete(self, key: K) -> bool:
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def max_size(self) -> int:
        return self._max_size

    def keys(self):
        return self._cache.keys()

    def values(self):
        return self._cache.values()

    def entries(self):
        return self._cache.items()

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "evictions": self._evictions,
        }

    def reset_stats(self) -> None:
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def resize(self, new_max_size: int) -> None:
        if new_max_size <= 0:
            raise ValueError(f"max_size must be positive, got {new_max_size}")
        self._max_size = new_max_size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
            self._evictions += 1


class LRUCacheWithTTL[K, V]:
    """LRU cache with time-to-live expiration per entry."""

    _cache: OrderedDict[K, tuple[V, float]]

    def __init__(self, max_size: int = 100, ttl_ms: float = 60_000) -> None:
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        if ttl_ms <= 0:
            raise ValueError(f"ttl_ms must be positive, got {ttl_ms}")
        self._max_size = max_size
        self._ttl_ms = ttl_ms
        self._cache: OrderedDict[K, tuple[V, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    def _now(self) -> float:
        return time.monotonic() * 1000

    def _is_expired(self, expires: float) -> bool:
        return expires > 0 and self._now() > expires

    def get(self, key: K) -> V | None:
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, expires = entry
        if self._is_expired(expires):
            self._cache.pop(key, None)
            self._misses += 1
            self._expirations += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: K, value: V, custom_ttl_ms: float | None = None) -> None:
        if key in self._cache:
            self._cache.pop(key)
        ttl = custom_ttl_ms if custom_ttl_ms is not None else self._ttl_ms
        expires = 0.0 if ttl == 0 else self._now() + ttl
        self._cache[key] = (value, expires)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
            self._evictions += 1

    def has(self, key: K) -> bool:
        entry = self._cache.get(key)
        if entry is None:
            return False
        _, expires = entry
        if self._is_expired(expires):
            self._cache.pop(key, None)
            return False
        return True

    def delete(self, key: K) -> bool:
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._expirations = 0
        self._evictions = 0

    @property
    def size(self) -> int:
        return len(self._cache)

    def purge_expired(self) -> int:
        purged = 0
        expired_keys = [k for k, (_, e) in self._cache.items() if self._is_expired(e)]
        for k in expired_keys:
            self._cache.pop(k, None)
            purged += 1
        self._expirations += purged
        return purged

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "evictions": self._evictions,
            "expirations": self._expirations,
            "ttl_ms": self._ttl_ms,
        }

    def reset_stats(self) -> None:
        self._hits = 0
        self._misses = 0
        self._expirations = 0
        self._evictions = 0

    def resize(self, new_max_size: int) -> None:
        if new_max_size <= 0:
            raise ValueError(f"max_size must be positive, got {new_max_size}")
        self._max_size = new_max_size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
            self._evictions += 1


def create_lru_cache(max_size: int = 100) -> LRUCache:
    return LRUCache(max_size)


def create_lru_cache_with_ttl(max_size: int = 100, ttl_ms: float = 60_000) -> LRUCacheWithTTL:
    return LRUCacheWithTTL(max_size, ttl_ms)
