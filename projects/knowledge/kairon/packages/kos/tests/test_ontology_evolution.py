"""Tests for KOS LLM Entity Extractor and Ontology Evolution."""

import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestLLMEntityExtractor(unittest.TestCase):
    """Test the LLMEntityExtractor class."""

    def test_import(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        self.assertTrue(callable(LLMEntityExtractor))

    def test_creation(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        self.assertIsNotNone(extractor)

    def test_json_extraction_plain(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        text = '{"entities": [{"label": "Test", "type": "Person"}], "relations": []}'
        result = extractor._extract_json(text)
        self.assertEqual(result, text)

    def test_json_extraction_markdown(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        text = '```json\n{"entities": [], "relations": []}\n```'
        result = extractor._extract_json(text)
        self.assertIn("entities", result)

    def test_parse_response_valid(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        response = """
        {
            "entities": [
                {"label": "夏明星", "type": "Person", "description": "项目参与者"},
                {"label": "数字化平台", "type": "Project", "description": "卫健委项目"}
            ],
            "relations": [
                {"source": "夏明星", "predicate": "works_on", "target": "数字化平台", "confidence": 0.9}
            ]
        }
        """
        result = extractor._parse_response(response)
        self.assertEqual(len(result["entities"]), 2)
        self.assertEqual(len(result["relations"]), 1)
        self.assertEqual(result["entities"][0]["label"], "夏明星")
        self.assertEqual(result["entities"][0]["type"], "Person")
        self.assertEqual(result["relations"][0]["predicate"], "works_on")

    def test_parse_response_empty(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        result = extractor._parse_response("")
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["relations"], [])

    def test_parse_response_invalid_json(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        result = extractor._parse_response("not json at all")
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["relations"], [])

    def test_build_extraction_prompt(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        prompt = extractor._build_extraction_prompt("测试文本内容")
        self.assertIn("测试文本内容", prompt)
        self.assertIn("entities", prompt)
        self.assertIn("relations", prompt)

    def test_build_extraction_prompt_with_existing(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        existing = [{"label": "已有实体", "type": "Person"}]
        prompt = extractor._build_extraction_prompt("测试文本", existing_entities=existing)
        self.assertIn("已有实体", prompt)

    def test_combine_docs(self):
        from kos.ontology.llm_extractor import LLMEntityExtractor

        extractor = LLMEntityExtractor()
        docs = [
            {"text": "文档1内容"},
            {"text": "文档2内容"},
        ]
        combined = extractor._combine_docs(docs)
        self.assertIn("文档1内容", combined)
        self.assertIn("文档2内容", combined)


class TestOntologyEvolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # CI 干净环境无 kos_relations 表 (本地运行态掩盖) — schema 自初始化
        from kos.ontology.schema import init_schema

        try:
            # 用 OntologyEvolution 同源 GraphRAG 连接 init (免路径解析分叉)
            from kos.graphrag import GraphRAG

            with GraphRAG() as rag:
                init_schema(rag.conn)
        except Exception:
            pass  # 已初始化或环境不支持时跳过
    """Test the OntologyEvolution class."""

    def test_import(self):
        from kos.ontology.evolution import OntologyEvolution

        self.assertTrue(callable(OntologyEvolution))

    def test_creation(self):
        from kos.ontology.evolution import OntologyEvolution

        evo = OntologyEvolution()
        self.assertIsNotNone(evo)

    def test_get_stats(self):
        # 干净环境无实体数据 (本地运行态掩盖) — 先种子一条保证统计非零
        from kos.graphrag import get_connection
        from kos.ontology.evolution import OntologyEvolution

        conn = get_connection(None)
        conn.execute(
            "INSERT OR IGNORE INTO kos_entities (entity_id, entity_type, label) VALUES (?, ?, ?)",
            ("test:seed-entity", "test", "seed"),
        )
        conn.commit()

        evo = OntologyEvolution()
        stats = evo.get_stats()
        self.assertIn("entities", stats)
        self.assertIn("relations", stats)
        self.assertIn("entity_doc_links", stats)
        self.assertIn("type_distribution", stats)
        self.assertGreater(stats["entities"], 0)

    def test_evolve(self):
        from kos.ontology.evolution import OntologyEvolution

        evo = OntologyEvolution()
        report = evo.evolve()
        self.assertIn("timestamp", report)
        self.assertIn("deduplication", report)
        self.assertIn("type_normalization", report)
        self.assertIn("orphan_detection", report)
        self.assertIn("relation_conflicts", report)

    def test_get_recommendations(self):
        from kos.ontology.evolution import OntologyEvolution

        evo = OntologyEvolution()
        recs = evo.get_recommendations()
        self.assertIsInstance(recs, list)

    def test_type_normalization_map(self):
        from kos.ontology.evolution import OntologyEvolution

        self.assertIn("concept", OntologyEvolution.TYPE_NORMALIZATION)
        self.assertEqual(OntologyEvolution.TYPE_NORMALIZATION["concept"], "Concept")
        self.assertEqual(OntologyEvolution.TYPE_NORMALIZATION["person"], "Person")
        self.assertEqual(OntologyEvolution.TYPE_NORMALIZATION["org"], "Organization")


if __name__ == "__main__":
    unittest.main()
