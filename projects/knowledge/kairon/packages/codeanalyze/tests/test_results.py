"""Tests for core/results.py — Entity, Relation, KnowledgeGraph data model."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeanalyze.core.results import Entity, KnowledgeGraph, Provenance, Relation


class TestEntity:
    def test_create_entity(self):
        e = Entity(id="test-1", name="测试实体", type="Document", source="official")
        assert e.id == "test-1"
        assert e.name == "测试实体"
        assert e.type == "Document"
        assert e.domain == "通用"

    def test_entity_with_provenance(self):
        prov = Provenance(
            source_file="/path/to/doc.pdf",
            analyzer="pdftotext",
            method="regex+pdftotext",
            confidence=0.9,
        )
        e = Entity(
            id="test-2",
            name="带溯源实体",
            type="Policy",
            source="official",
            provenance=prov,
        )
        assert e.provenance is not None
        assert e.provenance.source_file == "/path/to/doc.pdf"
        assert e.provenance.analyzer == "pdftotext"

    def test_entity_to_dict(self):
        e = Entity(id="test-3", name="DictTest", type="Organization", source="official")
        d = e.to_dict()
        assert d["id"] == "test-3"
        assert d["name"] == "DictTest"
        assert d["provenance"]["source_file"] == ""
        assert d["provenance"]["analyzer"] == "official"

    def test_entity_json_ld(self):
        e = Entity(id="test-4", name="JSONLD", type="Document", source="official")
        ld = e.to_json_ld(graph_url="https://example.com/kg")
        assert "@id" in ld
        assert "https://example.com/kg/entity/test-4" in ld["@id"]
        assert "schema:Thing" in ld["@type"]


class TestRelation:
    def test_create_relation(self):
        r = Relation(source_id="src-1", target_id="tgt-1", type="REFERENCES")
        assert r.source_id == "src-1"
        assert r.target_id == "tgt-1"
        assert r.type == "REFERENCES"

    def test_relation_domain_from_type(self):
        r = Relation(source_id="a", target_id="b", type="IMPORTS")
        d = r.to_dict()
        assert d["domain"] == "代码"

    def test_relation_with_provenance(self):
        prov = Provenance(analyzer="graphify", method="tree-sitter")
        r = Relation(source_id="a", target_id="b", type="CALLS", provenance=prov)
        d = r.to_dict()
        assert "provenance" in d
        assert d["provenance"]["analyzer"] == "graphify"


class TestKnowledgeGraph:
    def test_empty_graph(self):
        kg = KnowledgeGraph()
        assert kg.entity_count == 0
        assert kg.relation_count == 0

    def test_add_entity_and_relation(self):
        kg = KnowledgeGraph()
        e1 = Entity(id="e1", name="Entity1", type="Document", source="test")
        e2 = Entity(id="e2", name="Entity2", type="Policy", source="test")
        kg.add_entity(e1)
        kg.add_entity(e2)
        kg.add_relation(Relation(source_id="e1", target_id="e2", type="REFERENCES"))
        assert kg.entity_count == 2  # e1 + e2
        # add_entity also creates SourceFile + EXTRACTED_FROM if source_path set
        assert kg.relation_count >= 1

    def test_add_entity_with_source_file(self):
        kg = KnowledgeGraph()
        e = Entity(
            id="e-src",
            name="SrcEntity",
            type="Document",
            source="test",
            source_path="/path/to/file.pdf",
        )
        kg.add_entity(e, source_file="/path/to/file.pdf")
        # should create SourceFile entity + EXTRACTED_FROM relation
        source_files = [e for e in kg.entities.values() if e.type == "SourceFile"]
        assert len(source_files) >= 1
        extracted = [r for r in kg.relations if r.type == "EXTRACTED_FROM"]
        assert len(extracted) >= 1

    def test_merge(self):
        kg1 = KnowledgeGraph()
        kg1.entities["shared"] = Entity(id="shared", name="Shared", type="Document", source="a")
        kg2 = KnowledgeGraph()
        kg2.entities["unique"] = Entity(id="unique", name="Unique", type="Document", source="b")
        kg1.merge(kg2)
        assert "unique" in kg1.entities
        # shared + unique (+ any SourceFiles created during merge)
        assert len(kg1.entities) >= 2

    def test_to_json(self):
        kg = KnowledgeGraph(metadata={"test": True})
        kg.add_entity(Entity(id="j1", name="J1", type="Document", source="test"))
        j = json.loads(kg.to_json())
        assert "entities" in j
        assert "relations" in j
        assert j["metadata"]["test"] is True

    def test_to_cypher(self):
        kg = KnowledgeGraph(metadata={"project": "test"})
        kg.add_entity(Entity(id="cy-1", name="Cypher1", type="Document", source="test"))
        kg.add_entity(Entity(id="cy-2", name="Cypher2", type="Policy", source="test"))
        kg.add_relation(Relation(source_id="cy-1", target_id="cy-2", type="REFERENCES"))
        cypher = kg.to_cypher()
        assert "MERGE" in cypher
        assert "REFERENCES" in cypher
        assert "cy-1" in cypher

    def test_entity_types_taxonomy(self):
        from codeanalyze.core.results import ENTITY_TYPES

        assert "Document" in ENTITY_TYPES
        assert "Function" in ENTITY_TYPES
        assert "Organization" in ENTITY_TYPES

    def test_relation_types_taxonomy(self):
        from codeanalyze.core.results import RELATION_TYPES

        assert "REFERENCES" in RELATION_TYPES
        assert RELATION_TYPES["REFERENCES"]["label"] == "引用"
        assert RELATION_TYPES["REFERENCES"]["domain"] == "文档"
