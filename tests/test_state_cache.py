"""测试 StateCache"""

import time
from pathlib import Path
from tempfile import TemporaryDirectory

from omo.state_cache import GovernanceStateCache


def test_basic_cache():
    with TemporaryDirectory() as tmpdir:
        cache = GovernanceStateCache(Path(tmpdir))
        cache.cache_state("test-key", "test-value")
        value = cache.get_cached_state("test-key")
        assert value == "test-value"


def test_cache_expiration():
    with TemporaryDirectory() as tmpdir:
        cache = GovernanceStateCache(Path(tmpdir))
        cache.cache_state("temp", "expire-me", ttl_seconds=1)
        time.sleep(2)
        value = cache.get_cached_state("temp")
        assert value is None


def test_cache_stats():
    with TemporaryDirectory() as tmpdir:
        cache = GovernanceStateCache(Path(tmpdir))
        cache.cache_state("k1", "v1")
        cache.cache_state("k2", "v2")
        stats = cache.get_cache_stats()
        assert stats["total_entries"] == 2
