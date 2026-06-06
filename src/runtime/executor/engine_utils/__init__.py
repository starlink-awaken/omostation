"""Engine utility package — cache, object pool, and stats."""

from __future__ import annotations

from runtime.executor.engine_utils.cache import LRUCache, LRUCacheWithTTL, create_lru_cache, create_lru_cache_with_ttl
from runtime.executor.engine_utils.pool import ObjectPool
from runtime.executor.engine_utils.stats import (
    BenchmarkStats,
    calculate_stats,
    collect_samples,
    collect_samples_async,
    measure_time,
    measure_time_async,
)

__all__ = [
    "LRUCache",
    "LRUCacheWithTTL",
    "create_lru_cache",
    "create_lru_cache_with_ttl",
    "ObjectPool",
    "BenchmarkStats",
    "calculate_stats",
    "collect_samples",
    "collect_samples_async",
    "measure_time",
    "measure_time_async",
]
