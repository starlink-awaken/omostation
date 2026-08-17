"""Tests for integrations/eidos_adapter.py — Eidos format conversion."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeanalyze.core.results import Entity, KnowledgeGraph, Relation
from codeanalyze.integrations.eidos_adapter import (
    convert_kg,
    kg_to_eidos_cards,
    kg_to_eidos_facts,
    kg_to_eidos_nodes,
    kg_to_eidos_relations,
    try_eidos_validate,
)


def _make_test_kg() -> KnowledgeGraph:
    kg = KnowledgeGraph(metadata={"test": True})
    kg.add_entity(
        Entity(
            id="doc-test",
            name="TestDoc",
            type="Document",
            source="official",
            domain="文档",
            confidence=0.9,
            source_path="/path/to/test.pdf",
        )
    )
    kg.add_entity(
        Entity(
            id="docnum-〔2026〕1号",
            name="〔2026〕1号",
            type="Policy",
            source="official",
            domain="政策",
            confidence=0.95,
        )
    )
    kg.add_entity(
        Entity(
            id="org-test",
            name="TestOrg",
            type="Organization",
            source="official",
            domain="组织",
            confidence=0.8,
        )
    )
    kg.add_relation(
        Relation(
            source_id="doc-test",
            target_id="docnum-〔2026〕1号",
            type="REFERENCES",
        )
    )
    kg.add_relation(
        Relation(
            source_id="doc-test",
            target_id="org-test",
            type="BELONGS_TO",
        )
    )
    return kg


class TestConvertKG:
    def test_convert_nodes(self):
        kg = _make_test_kg()
        nodes = kg_to_eidos_nodes(kg)
        assert len(nodes) >= 3
        types = {n["node_type"] for n in nodes}
        assert "Document" in types
        assert "Policy" in types
        assert "Organization" in types

    def test_convert_nodes_have_required_fields(self):
        kg = _make_test_kg()
        nodes = kg_to_eidos_nodes(kg)
        for n in nodes:
            assert "id" in n
            assert "name" in n
            assert "node_type" in n
            assert "properties" in n

    def test_convert_relations(self):
        kg = _make_test_kg()
        rels = kg_to_eidos_relations(kg)
        assert len(rels) >= 2
        types = {r["relation_type"] for r in rels}
        assert "REFERENCES" in types
        assert "BELONGS_TO" in types

    def test_relations_have_meta(self):
        kg = _make_test_kg()
        rels = kg_to_eidos_relations(kg)
        for r in rels:
            assert r["meta_relation"] in ("struct", "derive", "behavior", "justify")

    def test_convert_facts(self):
        kg = _make_test_kg()
        facts = kg_to_eidos_facts(kg)
        assert len(facts) >= 2
        for f in facts:
            assert "subject" in f
            assert "predicate" in f
            assert "object" in f

    def test_convert_cards(self):
        kg = _make_test_kg()
        cards = kg_to_eidos_cards(kg)
        assert len(cards) >= 1
        for c in cards:
            assert "title" in c
            assert "source_type" in c

    def test_full_convert(self):
        kg = _make_test_kg()
        result = convert_kg(kg)
        assert "meta" in result
        assert "ontology_nodes" in result
        assert "relations" in result
        assert "facts" in result
        assert "cards" in result
        assert result["meta"]["entity_count"] >= 3

    def test_try_validate(self):
        """Eidos 校验（安装与否均不崩溃）。"""
        kg = _make_test_kg()
        data = convert_kg(kg)
        result = try_eidos_validate(data)
        # available 取决于 Eidos 是否安装，但必须返回 dict 不抛异常
        assert isinstance(result, dict)
        assert "schema_checks" in result or "available" in result
