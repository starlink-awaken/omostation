"""Tests for KOS query understanding, GraphRAG, and config center."""

import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestQueryUnderstanding(unittest.TestCase):
    """Test the QueryUnderstanding class."""

    def test_import(self):
        from kos.query import QueryUnderstanding

        self.assertTrue(callable(QueryUnderstanding))

    def test_analyze_basic(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        result = qu.analyze("数据治理")
        self.assertIn("original_query", result)
        self.assertIn("intent", result)
        self.assertIn("expanded_terms", result)
        self.assertEqual(result["original_query"], "数据治理")

    def test_analyze_time_range(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        result = qu.analyze("最近一周关于数据治理的通知")
        self.assertIsNotNone(result["time_range"])
        self.assertIn("start", result["time_range"])
        self.assertIn("end", result["time_range"])

    def test_analyze_intent_comparison(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        result = qu.analyze("数据治理 vs 信息治理")
        self.assertEqual(result["intent"], "comparison")

    def test_analyze_intent_precise(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        result = qu.analyze("关于数据治理的通知")
        self.assertEqual(result["intent"], "precise")

    def test_analyze_field_filters(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        result = qu.analyze("数据治理 kind:通知")
        self.assertIn("kind", result["filters"])

    def test_analyze_expansion(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        result = qu.analyze("数据治理")
        self.assertGreater(len(result["expanded_terms"]), 0)
        self.assertIn("信息治理", result["expanded_terms"])

    def test_analyze_enhanced_query(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        result = qu.analyze("数据治理")
        self.assertIn("数据治理", result["enhanced_query"])

    def test_time_patterns(self):
        from kos.query import QueryUnderstanding

        qu = QueryUnderstanding()
        time_queries = [
            "今天的报告",
            "昨天的通知",
            "最近一周的公文",
            "最近一个月的数据",
            "本月的考核",
        ]
        for q in time_queries:
            result = qu.analyze(q)
            self.assertIsNotNone(result["time_range"], f"Failed for: {q}")


class TestGraphRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # CI 干净环境无 kos_relations 表 (本地运行态掩盖) — schema 自初始化
        from kos.graphrag import get_connection
        from kos.ontology.schema import init_schema

        try:
            init_schema(get_connection(None))
        except Exception:
            pass  # 已初始化或环境不支持时跳过
    """Test the GraphRAG class."""

    def test_import(self):
        from kos.graphrag import GraphRAG

        self.assertTrue(callable(GraphRAG))

    def test_creation(self):
        from kos.graphrag import GraphRAG

        rag = GraphRAG()
        self.assertIsNotNone(rag)
        rag.close()

    def test_multi_hop_search(self):
        from kos.graphrag import GraphRAG

        with GraphRAG() as rag:
            result = rag.multi_hop_search("夏明星", hops=2, limit=5)
            self.assertIn("results", result)
            self.assertIn("paths", result)
            self.assertIn("start_entities", result)

    def test_find_path(self):
        from kos.graphrag import GraphRAG

        with GraphRAG() as rag:
            result = rag.find_path("P:xia-mingxing", "J:kairon", max_hops=3)
            self.assertIn("found", result)

    def test_discover_implicit(self):
        from kos.graphrag import GraphRAG

        with GraphRAG() as rag:
            result = rag.discover_implicit("夏明星", min_shared_docs=1)
            self.assertIn("associations", result)

    def test_context_manager(self):
        from kos.graphrag import GraphRAG

        with GraphRAG() as rag:
            self.assertIsNotNone(rag.conn)


class TestConfigCenter(unittest.TestCase):
    """Test the ConfigCenter class."""

    def test_import(self):
        from kos.config_center import ConfigCenter

        self.assertTrue(callable(ConfigCenter))

    def test_creation(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        self.assertIsNotNone(center)

    def test_get_default(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        model = center.get("embedding.model")
        self.assertIsNotNone(model)

    def test_get_nested(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        mode = center.get("search.default_mode")
        self.assertEqual(mode, "hybrid")

    def test_get_nonexistent(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        value = center.get("nonexistent.key")
        self.assertIsNone(value)

    def test_get_default_value(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        value = center.get("nonexistent.key", "default")
        self.assertEqual(value, "default")

    def test_set(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        center.set("search.default_limit", 20)
        self.assertEqual(center.get("search.default_limit"), 20)

    def test_validate(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        result = center.validate()
        self.assertIn("valid", result)
        self.assertIn("errors", result)
        self.assertIn("warnings", result)

    def test_list(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        config = center.list()
        self.assertIn("embedding", config)
        self.assertIn("search", config)
        self.assertIn("indexing", config)

    def test_diff(self):
        from kos.config_center import ConfigCenter

        center = ConfigCenter()
        changes = center.diff()
        self.assertIsInstance(changes, dict)


if __name__ == "__main__":
    unittest.main()
