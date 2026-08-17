"""Tests for KOS Cache Manager and performance."""

import os
import sys
import time
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestLRUCache(unittest.TestCase):
    """Test the LRUCache class."""

    def test_import(self):
        from kos.cache import LRUCache

        self.assertTrue(callable(LRUCache))

    def test_set_get(self):
        from kos.cache import LRUCache

        cache = LRUCache(capacity=10, default_ttl=60)
        cache.set("key1", {"data": "value1"})
        result = cache.get("key1")
        self.assertEqual(result["data"], "value1")  # type: ignore[reportOptionalSubscript]

    def test_miss(self):
        from kos.cache import LRUCache

        cache = LRUCache(capacity=10, default_ttl=60)
        result = cache.get("nonexistent")
        self.assertIsNone(result)

    def test_eviction(self):
        from kos.cache import LRUCache

        cache = LRUCache(capacity=3, default_ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict "a"
        self.assertIsNone(cache.get("a"))
        self.assertIsNotNone(cache.get("d"))

    def test_expiration(self):
        from kos.cache import LRUCache

        cache = LRUCache(capacity=10, default_ttl=0.1)
        cache.set("key", "value")
        time.sleep(0.15)
        result = cache.get("key")
        self.assertIsNone(result)

    def test_stats(self):
        from kos.cache import LRUCache

        cache = LRUCache(capacity=10, default_ttl=60)
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.stats
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)

    def test_clear(self):
        from kos.cache import LRUCache

        cache = LRUCache(capacity=10, default_ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        self.assertEqual(cache.stats["size"], 0)

    def test_invalidate(self):
        from kos.cache import LRUCache

        cache = LRUCache(capacity=10, default_ttl=60)
        cache.set("a", 1)
        self.assertTrue(cache.invalidate("a"))
        self.assertFalse(cache.invalidate("a"))
        self.assertIsNone(cache.get("a"))


class TestSearchCache(unittest.TestCase):
    """Test the SearchCache class."""

    def test_import(self):
        from kos.cache import SearchCache

        self.assertTrue(callable(SearchCache))

    def test_creation(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        self.assertIsNotNone(cache)

    def test_set_get(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        cache.set("test query", "keyword", [{"doc_id": "1", "title": "Test"}])
        result = cache.get("test query", "keyword")
        self.assertIsNotNone(result)
        self.assertEqual(result["cache_hit"], "L1")  # type: ignore[reportOptionalSubscript]

    def test_miss(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        result = cache.get("nonexistent query", "keyword")
        self.assertIsNone(result)

    def test_different_modes(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        cache.set("query", "keyword", [{"doc_id": "1"}])
        cache.set("query", "semantic", [{"doc_id": "2"}])
        r1 = cache.get("query", "keyword")
        r2 = cache.get("query", "semantic")
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)

    def test_different_limits(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        cache.set("query", "keyword", [{"doc_id": "1"}], limit=5)
        result = cache.get("query", "keyword", limit=10)
        self.assertIsNone(result)  # Different limit = different key

    def test_stats(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        cache.set("q1", "keyword", [{"doc_id": "1"}])
        stats = cache.get_stats()
        self.assertIn("l1_memory", stats)
        self.assertIn("l2_persistent", stats)

    def test_clear_all(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        cache.set("q1", "keyword", [{"doc_id": "1"}])
        cache.clear_all()
        self.assertIsNone(cache.get("q1", "keyword"))

    def test_search_with_cache(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        result = cache.search_with_cache("测试", mode="keyword", limit=3)
        self.assertIn("results", result)
        self.assertGreater(result["count"], 0)

    def test_search_with_cache_hit(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        # First call populates cache
        cache.search_with_cache("测试", mode="keyword", limit=3)
        # Second call should hit cache
        result = cache.search_with_cache("测试", mode="keyword", limit=3)
        self.assertEqual(result.get("cache_hit"), "L1")

    def test_invalidate(self):
        from kos.cache import SearchCache

        cache = SearchCache()
        cache.set("query", "keyword", [{"doc_id": "1"}])
        cache.invalidate("query", "keyword")
        self.assertIsNone(cache.get("query", "keyword"))


class TestCacheIntegration(unittest.TestCase):
    """Test cache integration with search engine."""

    def test_engine_caching(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        # First search
        r1 = engine.search("integration_test", mode="keyword", limit=3, use_cache=True)
        self.assertGreater(r1["count"], 0)
        # Second search should hit cache
        r2 = engine.search("integration_test", mode="keyword", limit=3, use_cache=True)
        self.assertEqual(r2.get("cache_hit"), "L1")
        engine.close()

    def test_no_cache_option(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        r1 = engine.search("测试", mode="keyword", limit=3, use_cache=False)
        self.assertGreater(r1["count"], 0)
        self.assertIsNone(r1.get("cache_hit"))
        engine.close()


if __name__ == "__main__":
    unittest.main()
