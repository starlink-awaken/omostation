"""Tests for KOS Context Engine and Memory Tier."""

import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestContextEngine(unittest.TestCase):
    """Test the ContextEngine class."""

    def test_import(self):
        from kos.context_engine import ContextEngine

        self.assertTrue(callable(ContextEngine))

    def test_engine_creation(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        self.assertIsNotNone(engine)
        engine.close()

    def test_build_context_concise(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        ctx = engine.build_context("test", mode="concise")
        self.assertIn("sections", ctx)
        self.assertIn("total_tokens", ctx)
        self.assertIn("mode", ctx)
        self.assertEqual(ctx["mode"], "concise")
        # Concise should have fewer tokens
        self.assertLessEqual(ctx["total_tokens"], 1000)
        engine.close()

    def test_build_context_balanced(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        ctx = engine.build_context("test", mode="balanced")
        self.assertIn("sections", ctx)
        self.assertGreater(ctx["total_tokens"], 0)
        engine.close()

    def test_build_context_detailed(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        ctx = engine.build_context("test", mode="detailed")
        self.assertIn("sections", ctx)
        # Detailed should allow more tokens
        self.assertLessEqual(ctx["total_tokens"], 4000)
        engine.close()

    def test_build_context_with_persona(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        ctx = engine.build_context("test", mode="balanced", persona="架构师")
        # Should have persona section
        section_types = [s["type"] for s in ctx["sections"]]
        self.assertIn("persona", section_types)
        engine.close()

    def test_build_context_with_history(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        ctx = engine.build_context(
            "test",
            mode="detailed",
            history=["query1", "query2"],
        )
        # Should have history section in detailed mode
        section_types = [s["type"] for s in ctx["sections"]]
        self.assertIn("history", section_types)
        engine.close()

    def test_build_context_for_agent(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        prompt = engine.build_context_for_agent("测试任务", persona="开发者")
        self.assertIsInstance(prompt, str)
        self.assertIn("测试任务", prompt)
        self.assertIn("开发者", prompt)
        engine.close()

    def test_token_estimation(self):
        from kos.context_engine import ContextEngine

        # Chinese text
        tokens_cn = ContextEngine._estimate_tokens("中文测试文本")
        self.assertGreater(tokens_cn, 0)
        # English text
        tokens_en = ContextEngine._estimate_tokens("Hello world test")
        self.assertGreater(tokens_en, 0)
        # Empty
        self.assertEqual(ContextEngine._estimate_tokens(""), 0)

    def test_custom_max_tokens(self):
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        ctx = engine.build_context("test", mode="detailed", max_tokens=500)
        self.assertLessEqual(ctx["total_tokens"], 600)  # Allow small overflow
        engine.close()

    def test_context_manager(self):
        from kos.context_engine import ContextEngine

        with ContextEngine() as engine:
            ctx = engine.build_context("test", mode="concise")
            self.assertIn("sections", ctx)


class TestMemoryTier(unittest.TestCase):
    """Test the MemoryTier class."""

    def test_import(self):
        from kos.memory_tier import MemoryTier

        self.assertTrue(callable(MemoryTier))

    def test_creation(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        self.assertIsNotNone(memory)

    def test_record_and_get_session(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        memory.record_search("test_query")
        history = memory.get_session_history()
        self.assertIn("test_query", history)

    def test_record_and_get_persistent(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        memory.record_search("persistent_query")
        history = memory.get_history(limit=10)
        queries = [h["query"] for h in history]
        self.assertIn("persistent_query", queries)

    def test_popular_queries(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        memory.record_search("popular_q")
        memory.record_search("popular_q")
        popular = memory.get_popular(limit=5)
        queries = [p["query"] for p in popular]
        self.assertIn("popular_q", queries)

    def test_clear_session(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        memory.record_search("query1")
        memory.clear_session()
        self.assertEqual(len(memory.get_session_history()), 0)

    def test_clear_history(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        memory.record_search("query1")
        result = memory.clear_history()
        self.assertEqual(result["action"], "clear")

    def test_get_stats(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        stats = memory.get_stats()
        self.assertIn("session_queries", stats)
        self.assertIn("total_history", stats)
        self.assertIn("history_path", stats)

    def test_get_recent_unique(self):
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        memory.record_search("unique1")
        memory.record_search("unique2")
        unique = memory.get_recent_unique(limit=5)
        self.assertIsInstance(unique, list)


class TestTokenBudget(unittest.TestCase):
    """Test token budget control."""

    def test_budget_modes(self):
        from kos.context_engine import ContextEngine

        self.assertIn("concise", ContextEngine.MODES)
        self.assertIn("balanced", ContextEngine.MODES)
        self.assertIn("detailed", ContextEngine.MODES)

        # Verify relative ordering
        self.assertLess(
            ContextEngine.MODES["concise"]["max_tokens"],
            ContextEngine.MODES["balanced"]["max_tokens"],
        )
        self.assertLess(
            ContextEngine.MODES["balanced"]["max_tokens"],
            ContextEngine.MODES["detailed"]["max_tokens"],
        )


if __name__ == "__main__":
    unittest.main()
