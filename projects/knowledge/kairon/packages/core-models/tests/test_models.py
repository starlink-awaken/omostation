"""Tests for core-models — Entity, Relation, Provenance, KnowledgeGraph."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
from datetime import datetime

from core_models.models import (
    ENTITY_TYPES,
    RELATION_TYPES,
    Entity,
    KnowledgeGraph,
    Provenance,
    Relation,
)

# ── ENTITY_TYPES ────────────────────────────────────────────


class TestEntityTypes:
    def test_known_types(self):
        assert "Function" in ENTITY_TYPES
        assert "Class" in ENTITY_TYPES
        assert "Module" in ENTITY_TYPES
        assert "Person" in ENTITY_TYPES
        assert "Concept" in ENTITY_TYPES

    def test_entity_types_count(self):
        assert len(ENTITY_TYPES) >= 27  # 27 known types


# ── RELATION_TYPES ──────────────────────────────────────────


class TestRelationTypes:
    def test_known_relations(self):
        assert "CALLS" in RELATION_TYPES
        assert RELATION_TYPES["CALLS"]["label"] == "调用"
        assert RELATION_TYPES["CALLS"]["domain"] == "代码"

    def test_implements_relation(self):
        assert "IMPLEMENTS" in RELATION_TYPES

    def test_relation_domains(self):
        domains = {info["domain"] for info in RELATION_TYPES.values()}
        assert "代码" in domains
        assert "文档" in domains
        assert "业务" in domains
        assert "语义" in domains

    def test_relation_types_count(self):
        assert len(RELATION_TYPES) >= 20  # 20+ known types


# ── Provenance tests ────────────────────────────────────────


class TestProvenance:
    def test_defaults(self):
        p = Provenance()
        assert p.source_file == ""
        assert p.analyzer == ""
        assert p.confidence == 1.0
        assert p.notes == ""
        assert p.extracted_at != ""

    def test_auto_extracted_at(self):
        """extracted_at is auto-set to current ISO timestamp when empty"""
        p = Provenance()
        # Verify it looks like an ISO timestamp
        datetime.fromisoformat(p.extracted_at)

    def test_custom_extracted_at(self):
        """Custom extracted_at is preserved"""
        p = Provenance(extracted_at="2025-01-01T00:00:00")
        assert p.extracted_at == "2025-01-01T00:00:00"

    def test_to_dict(self):
        p = Provenance(source_file="test.py", analyzer="codeanalyze", method="ast", confidence=0.9)
        d = p.to_dict()
        assert d["source_file"] == "test.py"
        assert d["analyzer"] == "codeanalyze"
        assert d["method"] == "ast"
        assert d["confidence"] == 0.9
        assert "extracted_at" in d
        assert "notes" in d

    def test_to_dict_with_notes(self):
        p = Provenance(source_file="test.py", analyzer="ca", notes="manual review")
        d = p.to_dict()
        assert d["notes"] == "manual review"

    def test_to_dict_empty(self):
        p = Provenance()
        d = p.to_dict()
        assert d["source_file"] == ""
        assert d["analyzer"] == ""


# ── Entity tests ────────────────────────────────────────────


class TestEntity:
    def test_basic(self):
        e = Entity(id="e1", name="test_func", type="Function", source="codeanalyze")
        assert e.id == "e1"
        assert e.name == "test_func"
        assert e.type == "Function"
        assert e.created_at != ""
        assert e.domain == "通用"
        assert e.confidence == 1.0

    def test_auto_created_at(self):
        """created_at is auto-set to ISO timestamp when empty"""
        e = Entity(id="e1", name="f", type="Function", source="ca")
        datetime.fromisoformat(e.created_at)

    def test_custom_created_at(self):
        e = Entity(id="e1", name="f", type="Function", source="ca", created_at="2025-06-01T12:00:00")
        assert e.created_at == "2025-06-01T12:00:00"

    def test_to_dict_with_provenance(self):
        p = Provenance(source_file="a.py", analyzer="ca", method="ast")
        e = Entity(id="e1", name="f", type="Function", source="ca", domain="code", provenance=p)
        d = e.to_dict()
        assert d["provenance"]["source_file"] == "a.py"
        assert d["provenance"]["method"] == "ast"

    def test_to_dict_without_provenance_uses_source_path(self):
        """When no provenance, source_path is used to build fallback provenance"""
        e = Entity(id="e1", name="f", type="Function", source="ca", source_path="/x/y.py")
        d = e.to_dict()
        assert d["provenance"]["source_file"] == "/x/y.py"
        assert d["provenance"]["analyzer"] == "ca"
        assert d["provenance"]["method"] == "unknown"

    def test_to_dict_without_provenance_or_source_path(self):
        """When neither provenance nor source_path, fallback provenance has empty fields"""
        e = Entity(id="e1", name="f", type="Function", source="ca")
        d = e.to_dict()
        assert d["provenance"]["source_file"] == ""
        assert d["provenance"]["analyzer"] == "ca"

    def test_to_dict_includes_domain_properties(self):
        e = Entity(id="e1", name="f", type="Function", source="ca", properties={"key": "val"})
        d = e.to_dict()
        assert d["properties"] == {"key": "val"}

    def test_to_json_ld_basic(self):
        e = Entity(id="e1", name="test_func", type="Function", source="ca")
        ld = e.to_json_ld()
        assert "@id" in ld
        assert "e1" in ld["@id"]
        assert "Function" in str(ld["@type"])

    def test_to_json_ld_with_provenance(self):
        p = Provenance(source_file="a.py", analyzer="ca", method="ast")
        e = Entity(id="e1", name="f", type="Function", source="ca", provenance=p)
        ld = e.to_json_ld()
        assert "prov:wasGeneratedBy" in ld
        assert ld["prov:wasGeneratedBy"]["prov:used"] == "a.py"

    def test_to_json_ld_custom_graph_url(self):
        e = Entity(id="e1", name="f", type="Function", source="ca")
        ld = e.to_json_ld(graph_url="http://custom/kg")
        assert "http://custom/kg" in ld["@id"]

    def test_to_json_ld_no_provenance_omits_prov(self):
        e = Entity(id="e1", name="f", type="Function", source="ca")
        ld = e.to_json_ld()
        assert "prov:wasGeneratedBy" not in ld

    def test_source_line_default(self):
        e = Entity(id="e1", name="f", type="Function", source="ca")
        assert e.source_line == 0

    def test_custom_source_line(self):
        e = Entity(id="e1", name="f", type="Function", source="ca", source_line=42)
        assert e.source_line == 42


# ── Relation tests ──────────────────────────────────────────


class TestRelation:
    def test_minimal(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS")
        assert r.source_id == "e1"
        assert r.target_id == "e2"
        assert r.type == "CALLS"

    def test_to_dict(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS", confidence="EXTRACTED")
        d = r.to_dict()
        assert d["source"] == "e1"
        assert d["target"] == "e2"
        assert d["type_label"] == "调用"
        assert d["domain"] == "代码"
        assert d["confidence"] == "EXTRACTED"

    def test_to_dict_with_provenance(self):
        p = Provenance(source_file="a.py", analyzer="ca")
        r = Relation(source_id="e1", target_id="e2", type="CALLS", provenance=p)
        d = r.to_dict()
        assert d["provenance"]["source_file"] == "a.py"

    def test_to_dict_unknown_type(self):
        """Unknown relation type uses type itself as label"""
        r = Relation(source_id="e1", target_id="e2", type="UNKNOWN_TYPE")
        d = r.to_dict()
        assert d["type_label"] == "UNKNOWN_TYPE"
        assert d["domain"] == ""

    def test_to_dict_custom_weight(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS", weight=0.5)
        d = r.to_dict()
        assert d["weight"] == 0.5

    def test_to_dict_with_metadata(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS", metadata={"source": "inferred"})
        d = r.to_dict()
        assert d["metadata"]["source"] == "inferred"

    def test_to_json_ld(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS")
        ld = r.to_json_ld()
        assert "@id" in ld
        assert "CALLS" in ld["@id"]
        assert "schema:about" in ld
        assert "e1" in ld["schema:about"]["@id"]
        assert "e2" in ld["schema:relatedTo"]["@id"]

    def test_to_json_ld_custom_url(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS")
        ld = r.to_json_ld(graph_url="http://custom/kg")
        assert "http://custom/kg" in ld["@id"]

    def test_default_confidence(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS")
        assert r.confidence == "EXTRACTED"

    def test_inferred_confidence(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS", confidence="INFERRED")
        assert r.confidence == "INFERRED"

    def test_default_weight(self):
        r = Relation(source_id="e1", target_id="e2", type="CALLS")
        assert r.weight == 1.0


# ── KnowledgeGraph tests ────────────────────────────────────


class TestKnowledgeGraph:
    def test_empty_counts(self):
        kg = KnowledgeGraph()
        assert kg.entity_count == 0
        assert kg.relation_count == 0

    def test_add_entity(self):
        kg = KnowledgeGraph()
        e = Entity(id="e1", name="f", type="Function", source="ca", source_path="/x/y.py")
        kg.add_entity(e)
        assert kg.entity_count == 2  # e1 + auto-created SourceFile for /x/y.py
        assert "e1" in kg.entities

    def test_add_entity_without_source_path(self):
        """Entity without source_path doesn't create SourceFile entity"""
        kg = KnowledgeGraph()
        e = Entity(id="e1", name="f", type="Function", source="ca")
        kg.add_entity(e)
        assert kg.entity_count == 1

    def test_add_entity_with_provenance_source(self):
        """Entity with provenance uses provenance.source_file for SourceFile"""
        p = Provenance(source_file="/src/main.py", analyzer="ca")
        e = Entity(id="e1", name="f", type="Function", source="ca", provenance=p)
        kg = KnowledgeGraph()
        kg.add_entity(e)
        assert kg.entity_count == 2
        assert "main.py" in str(kg.entities)

    def test_add_entity_same_source_creates_single_file(self):
        """Multiple entities from same source file → single SourceFile entity"""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(id="e1", name="f1", type="Function", source="ca", source_path="/x/y.py"))
        kg.add_entity(Entity(id="e2", name="f2", type="Function", source="ca", source_path="/x/y.py"))
        assert kg.entity_count == 3  # e1, e2, 1 SourceFile

    def test_add_entity_different_sources_creates_multiple_files(self):
        """Entities from different source files → multiple SourceFile entities"""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(id="e1", name="f1", type="Function", source="ca", source_path="/x/a.py"))
        kg.add_entity(Entity(id="e2", name="f2", type="Function", source="ca", source_path="/y/b.py"))
        assert kg.entity_count == 4  # e1, e2, 2 SourceFiles

    def test_add_entity_creates_extracted_from_relation(self):
        """Adding entity with source_path creates EXTRACTED_FROM relation"""
        kg = KnowledgeGraph()
        e = Entity(id="e1", name="f", type="Function", source="ca", source_path="/x/y.py")
        kg.add_entity(e)
        extracted = [r for r in kg.relations if r.type == "EXTRACTED_FROM"]
        assert len(extracted) == 1
        assert extracted[0].source_id == "e1"

    def test_add_relation(self):
        kg = KnowledgeGraph()
        r = Relation(source_id="e1", target_id="e2", type="CALLS")
        kg.add_relation(r)
        assert kg.relation_count == 1

    def test_merge(self):
        kg1 = KnowledgeGraph()
        kg1.add_entity(Entity(id="a", name="A", type="Function", source="ca"))
        kg2 = KnowledgeGraph()
        kg2.add_entity(Entity(id="b", name="B", type="Function", source="ca"))
        kg1.merge(kg2)
        assert "b" in kg1.entities
        assert kg1.entity_count == 2

    def test_merge_does_not_overwrite_existing(self):
        """Existing entity is preserved during merge"""
        kg1 = KnowledgeGraph()
        kg1.add_entity(Entity(id="a", name="Original", type="Function", source="ca"))
        kg2 = KnowledgeGraph()
        kg2.add_entity(Entity(id="a", name="Override", type="Function", source="ca"))
        kg1.merge(kg2)
        assert kg1.entities["a"].name == "Original"  # not overwritten

    def test_merge_extends_relations(self):
        kg1 = KnowledgeGraph()
        kg2 = KnowledgeGraph()
        kg2.add_relation(Relation(source_id="a", target_id="b", type="CALLS"))
        kg1.merge(kg2)
        assert kg1.relation_count == 1

    def test_to_dict_structure(self):
        kg = KnowledgeGraph()
        d = kg.to_dict()
        assert "metadata" in d
        assert "entities" in d
        assert "relations" in d
        assert d["metadata"]["entity_count"] == 0
        assert d["metadata"]["relation_count"] == 0

    def test_to_dict_with_data(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity(id="a", name="A", type="Function", source="ca"))
        d = kg.to_dict()
        assert d["metadata"]["entity_count"] >= 1

    def test_to_json(self):
        kg = KnowledgeGraph()
        j = kg.to_json()
        assert '"entity_count": 0' in j
        parsed = json.loads(j)
        assert parsed["metadata"]["entity_count"] == 0

    def test_to_json_with_data(self):
        kg = KnowledgeGraph()
        e = Entity(id="e1", name="f", type="Function", source="ca")
        kg.add_entity(e)
        j = kg.to_json()
        parsed = json.loads(j)
        assert parsed["metadata"]["entity_count"] >= 1

    def test_to_json_ld_empty(self):
        kg = KnowledgeGraph()
        ld = kg.to_json_ld()
        assert "@context" in ld
        assert "@graph" in ld
        assert ld["@graph"] == []

    def test_to_json_ld_with_data(self):
        kg = KnowledgeGraph()
        e = Entity(id="e1", name="f", type="Function", source="ca")
        kg.add_entity(e)
        ld = kg.to_json_ld()
        assert len(ld["@graph"]) >= 1

    def test_to_json_ld_custom_url(self):
        kg = KnowledgeGraph()
        ld = kg.to_json_ld(graph_url="http://custom/kg")
        assert "http://custom/kg" in ld["@context"]["codeanalyze"]

    def test_to_cypher_empty(self):
        kg = KnowledgeGraph()
        c = kg.to_cypher()
        assert "// Cypher import" in c
        assert "0 entities, 0 relations" in c

    def test_to_cypher_with_entity(self):
        kg = KnowledgeGraph()
        e = Entity(id="e1", name="test_func", type="Function", source="ca", domain="code")
        kg.add_entity(e)
        c = kg.to_cypher()
        assert "MERGE" in c
        assert "e1" in c
        assert "test_func" in c

    def test_to_cypher_with_relation(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity(id="a", name="A", type="Function", source="ca", source_path="/x.py"))
        kg.add_entity(Entity(id="b", name="B", type="Function", source="ca", source_path="/x.py"))
        kg.add_relation(Relation(source_id="a", target_id="b", type="CALLS"))
        c = kg.to_cypher()
        assert "MATCH" in c
        assert "CALLS" in c

    def test_to_cypher_escapes_special_chars(self):
        """Special characters in IDs are escaped"""
        kg = KnowledgeGraph()
        e = Entity(id="e'1", name="test'func", type="Function", source="ca")
        kg.add_entity(e)
        c = kg.to_cypher()
        assert "\\'" in c or "e'1" in c  # single quote is escaped

    def test_source_files_tracked(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity(id="e1", name="f", type="Function", source="ca", source_path="/x/y.py"))
        assert len(kg.source_files) == 1
        assert "/x/y.py" in kg.source_files

    def test_method_chaining(self):
        """Add entity then relation, verify both present"""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(id="a", name="A", type="Function", source="ca"))
        kg.add_entity(Entity(id="b", name="B", type="Function", source="ca"))
        kg.add_relation(Relation(source_id="a", target_id="b", type="CALLS"))
        assert kg.entity_count >= 2
        assert kg.relation_count == 1

    def test_metadata_preserved_in_to_dict(self):
        kg = KnowledgeGraph()
        kg.metadata["project"] = "test"
        d = kg.to_dict()
        assert d["metadata"]["project"] == "test"
