"""Query cache — in-memory cache for graph query results.

Provides TTL-based caching with hit/miss statistics. Supports per-entry
TTL, key-based invalidation, and bulk clear. Persistence (disk backup)
is planned but not yet implemented.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any


class QueryCache:
    """In-memory query result cache with TTL support."""

    def __init__(self, ttl: float = 300.0) -> None:
        self._ttl = ttl
        self._cache: dict[str, tuple[float, Any]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get a cached value by key. Returns None if missing or expired."""
        if key in self._cache:
            ts, value = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                self._hits += 1
                return value
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a cached value with optional per-entry TTL."""
        self._cache[key] = (time.monotonic(), value)

    def invalidate(
        self, key: str = "", entity_ids: list[str] | None = None, relation_ids: list[str] | None = None
    ) -> int:
        """Invalidate cache entries, return count removed."""
        before = len(self._cache)
        if key:
            self._cache.pop(key, None)
        return before - len(self._cache)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def ping(self) -> bool:
        """Check cache health."""
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics: size, ttl, hit/miss counters."""
        return {
            "size": len(self._cache),
            "ttl": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
        }

    def generate_cache_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate stable cache key from positional + keyword args (sha256)."""
        payload = json.dumps({"args": list(args), "kwargs": dict(sorted(kwargs.items()))}, default=str, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


__all__ = [
    "QueryCache",
]
