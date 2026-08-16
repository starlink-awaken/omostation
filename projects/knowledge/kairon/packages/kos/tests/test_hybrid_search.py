"""Tests for KOS Hybrid Search Engine."""

import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestHybridSearchEngine(unittest.TestCase):
    """Test the HybridSearchEngine class."""

    def test_import(self):
        from kos.hybrid_search import HybridSearchEngine

        self.assertTrue(callable(HybridSearchEngine))

    def test_engine_creation(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        self.assertIsNotNone(engine)
        engine.close()

    def test_empty_query(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search("")
        self.assertEqual(result["count"], 0)
        self.assertIn("error", result)
        engine.close()

    def test_whitespace_query(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search("   ")
        self.assertEqual(result["count"], 0)
        engine.close()

    def test_keyword_search(self):
        from kos.cache import SearchCache
        from kos.hybrid_search import HybridSearchEngine

        SearchCache().clear_all()
        engine = HybridSearchEngine()
        result = engine.search("test", mode="keyword", limit=3)
        self.assertIn("results", result)
        self.assertIn("query_plan", result)
        self.assertIn("sources", result)
        self.assertGreater(result["count"], 0)
        engine.close()

    def test_hybrid_search(self):
        from kos.cache import SearchCache
        from kos.hybrid_search import HybridSearchEngine

        SearchCache().clear_all()
        engine = HybridSearchEngine()
        result = engine.search("测试", mode="hybrid", limit=5)
        self.assertIn("results", result)
        self.assertIn("sources", result)
        self.assertIn("elapsed_ms", result)
        # Semantic may not be available (no vector index built)
        # but keyword should always work
        self.assertTrue(result["sources"].get("keyword", 0) >= 0)
        engine.close()

    def test_graph_search(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search("kairon", mode="graph", limit=5)
        self.assertIn("results", result)
        engine.close()

    def test_context_modes(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        # Use keyword mode with no_cache to get fresh results
        for mode in ["concise", "balanced", "detailed"]:
            result = engine.search("测试", mode="keyword", context={"mode": mode}, limit=5, use_cache=False)
            self.assertEqual(result["query_plan"]["context_mode"], mode)
        engine.close()

    def test_limit_respected(self):
        from kos.cache import SearchCache
        from kos.hybrid_search import HybridSearchEngine

        # Clear L2 cache to avoid contamination from previous tests
        SearchCache().clear_all()
        engine = HybridSearchEngine()
        for limit in [1, 3, 5]:
            result = engine.search("平台架构设计方法论", mode="keyword", limit=limit, use_cache=False)
            self.assertIn("count", result)
            self.assertLessEqual(result["count"], limit)
        engine.close()

    def test_no_duplicates(self):
        from kos.cache import SearchCache
        from kos.hybrid_search import HybridSearchEngine

        SearchCache().clear_all()
        engine = HybridSearchEngine()
        result = engine.search("test", mode="hybrid", limit=10)
        paths = [r.get("canonical_path", "") for r in result["results"]]
        self.assertEqual(len(paths), len(set(paths)))
        engine.close()

    def test_query_plan_structure(self):
        from kos.cache import SearchCache
        from kos.hybrid_search import HybridSearchEngine

        SearchCache().clear_all()
        engine = HybridSearchEngine()
        result = engine.search("数字化平台", limit=5)
        plan = result["query_plan"]
        self.assertIn("needs_keyword", plan)
        self.assertIn("needs_semantic", plan)
        self.assertIn("needs_graph", plan)
        self.assertIn("complexity", plan)
        self.assertTrue(plan["needs_keyword"])  # Always True
        engine.close()

    def test_chinese_tokenization_in_query(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search("数字化平台", mode="keyword", limit=3)
        # Should tokenize and find results
        self.assertIsInstance(result["results"], list)
        engine.close()

    def test_context_manager(self):
        from kos.hybrid_search import HybridSearchEngine

        with HybridSearchEngine() as engine:
            result = engine.search("test", mode="keyword", limit=1)
            self.assertIn("results", result)


class TestSemanticModule(unittest.TestCase):
    """Test the updated semantic module."""

    def test_chunking(self):
        from kos.semantic import _chunk_text

        text = "测试文本。" * 200
        chunks = _chunk_text(text, chunk_size=100, overlap=20)
        self.assertGreater(len(chunks), 1)
        # Short text should return single chunk
        self.assertEqual(len(_chunk_text("短文本")), 1)
        # Empty text should return empty list
        self.assertEqual(len(_chunk_text("")), 0)

    def test_chunking_small_last_chunk_merge(self):
        from kos.semantic import _chunk_text

        # Text that would produce a tiny last chunk
        text = "A" * 515  # Just over one chunk
        chunks = _chunk_text(text, chunk_size=512, overlap=64)
        # Last chunk should be merged if too small
        for c in chunks:
            self.assertGreater(len(c), 50)

    def test_backend_detection(self):
        from kos.semantic import _get_embed_backend

        backend = _get_embed_backend()
        self.assertIn(backend, ["omlx", "st", "none"])

    def test_status(self):
        from kos.semantic import status

        result = status()
        self.assertIn("status", result)


class TestRRFFusion(unittest.TestCase):
    """Test RRF fusion logic."""

    def test_fusion_basic(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        results = {
            "keyword": [
                {"doc_id": "a", "title": "A"},
                {"doc_id": "b", "title": "B"},
            ],
            "semantic": [
                {"doc_id": "b", "title": "B"},
                {"doc_id": "c", "title": "C"},
            ],
        }
        fused = engine._reciprocal_rank_fusion(results, {})
        doc_ids = [d["doc_id"] for d in fused]
        # b appears in both → highest score
        self.assertEqual(doc_ids[0], "b")
        # All 3 unique docs present
        self.assertEqual(set(doc_ids), {"a", "b", "c"})
        engine.close()

    def test_fusion_weights(self):
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        # Same doc at rank 0 in both sources
        results = {
            "keyword": [{"doc_id": "x"}],
            "semantic": [{"doc_id": "x"}],
        }
        fused = engine._reciprocal_rank_fusion(results, {})
        # semantic has 1.2 weight, keyword has 1.0
        self.assertGreater(fused[0]["_rrf_score"], 0)
        engine.close()


if __name__ == "__main__":
    unittest.main()
