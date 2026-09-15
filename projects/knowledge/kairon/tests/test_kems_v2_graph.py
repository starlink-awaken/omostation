"""Unit tests for KEMS-v2 knowledge graph module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from kairon.graph.kems_v2 import (
    Edge,
    Entity,
    EntityType,
    KnowledgeGraph,
    RelationType,
    _tokenize,
)


# ── Fixtures ──


def _make_entity(
    eid: str = "pol-001",
    entity_type: EntityType = EntityType.POLICY,
    title: str = "Test Policy",
    content: str = "Test content about health policy",
    tags: list[str] | None = None,
) -> Entity:
    return Entity(
        id=eid,
        entity_type=entity_type,
        title=title,
        content=content,
        tags=tags or ["test"],
    )


def _make_edge(
    source: str = "pol-001",
    target: str = "reg-001",
    relation: RelationType = RelationType.CITES,
) -> Edge:
    return Edge(source_id=source, target_id=target, relation=relation)


def _populated_graph() -> KnowledgeGraph:
    """Graph with 6 entities and 5 edges for comprehensive testing."""
    g = KnowledgeGraph()
    entities = [
        _make_entity("pol-001", EntityType.POLICY, "卫生健康数字化转型政策", "推进卫生健康信息化建设", ["数字化", "政策"]),
        _make_entity("pol-002", EntityType.POLICY, "数据安全管理办法", "规范卫生健康数据管理", ["数据安全"]),
        _make_entity("reg-001", EntityType.REGULATION, "电子病历管理规程", "电子病历书写与管理规范", ["病历", "规程"]),
        _make_entity("reg-002", EntityType.REGULATION, "远程医疗管理办法", "互联网诊疗管理暂行办法", ["远程医疗"]),
        _make_entity("adr-001", EntityType.ADR, "ADR-001: 采用Neo4j图数据库", "决策使用Neo4j作为知识图谱存储", ["neo4j", "架构"]),
        _make_entity("app-001", EntityType.APPROVAL, "2024年度优秀批复-01", "关于加快推进医疗信息化的批复", ["批复", "信息化"]),
    ]
    for e in entities:
        g.add_entity(e)

    edges = [
        _make_edge("pol-001", "reg-001", RelationType.IMPLEMENTS),
        _make_edge("pol-001", "reg-002", RelationType.IMPLEMENTS),
        _make_edge("pol-002", "pol-001", RelationType.SUPERSEDES),
        _make_edge("reg-001", "adr-001", RelationType.CITES),
        _make_edge("app-001", "pol-001", RelationType.REFERENCES),
    ]
    for e in edges:
        g.add_edge(e)
    return g


# ── Tokenizer tests ──


class TestTokenize:
    def test_cjk_chars_are_individual_tokens(self):
        tokens = _tokenize("卫生健康")
        assert tokens == ["卫", "生", "健", "康"]

    def test_latin_lowercased(self):
        tokens = _tokenize("Neo4j Database")
        assert "neo4j" in tokens
        assert "database" in tokens

    def test_mixed_content(self):
        tokens = _tokenize("ADR-001 采用Neo4j")
        assert "adr" in tokens
        assert "001" in tokens
        assert "neo4j" in tokens
        assert "采" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []


# ── Entity tests ──


class TestEntity:
    def test_creation(self):
        e = _make_entity()
        assert e.id == "pol-001"
        assert e.entity_type == EntityType.POLICY

    def test_search_text(self):
        e = _make_entity(title="Title", content="Content", tags=["a", "b"])
        text = e.search_text
        assert "Title" in text
        assert "Content" in text
        assert "a" in text
        assert "b" in text

    def test_serialization_roundtrip(self):
        e = _make_entity()
        d = e.to_dict()
        assert d["entity_type"] == "policy"
        e2 = Entity.from_dict(d)
        assert e2.id == e.id
        assert e2.entity_type == e.entity_type
        assert e2.title == e.title


# ── Edge tests ──


class TestEdge:
    def test_creation(self):
        edge = _make_edge()
        assert edge.source_id == "pol-001"
        assert edge.relation == RelationType.CITES

    def test_serialization_roundtrip(self):
        edge = _make_edge()
        d = edge.to_dict()
        assert d["relation"] == "cites"
        e2 = Edge.from_dict(d)
        assert e2.source_id == edge.source_id
        assert e2.relation == edge.relation


# ── KnowledgeGraph tests ──


class TestKnowledgeGraph:
    def test_add_and_get_entity(self):
        g = KnowledgeGraph()
        e = _make_entity()
        g.add_entity(e)
        assert g.get_entity("pol-001") is e
        assert g.get_entity("nonexistent") is None

    def test_remove_entity(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        g.add_entity(_make_entity("b", title="B"))
        g.add_edge(_make_edge("a", "b"))
        assert g.remove_entity("a") is True
        assert g.get_entity("a") is None
        assert len(g.list_entities()) == 1
        assert len(g._edges) == 0

    def test_remove_nonexistent_entity(self):
        g = KnowledgeGraph()
        assert g.remove_entity("nope") is False

    def test_list_entities_by_type(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("p1", EntityType.POLICY))
        g.add_entity(_make_entity("r1", EntityType.REGULATION))
        g.add_entity(_make_entity("p2", EntityType.POLICY, title="P2"))
        assert len(g.list_entities(entity_type=EntityType.POLICY)) == 2
        assert len(g.list_entities(entity_type=EntityType.REGULATION)) == 1

    def test_list_entities_by_tags(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a", tags=["x", "y"]))
        g.add_entity(_make_entity("b", tags=["z"]))
        assert len(g.list_entities(tags=["x"])) == 1
        assert len(g.list_entities(tags=["x", "z"])) == 2

    def test_add_edge(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        g.add_entity(_make_entity("b", title="B"))
        edge = _make_edge("a", "b")
        g.add_edge(edge)
        assert len(g._edges) == 1

    def test_add_edge_missing_source(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("b", title="B"))
        with pytest.raises(ValueError, match="source entity not found"):
            g.add_edge(_make_edge("missing", "b"))

    def test_add_edge_missing_target(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        with pytest.raises(ValueError, match="target entity not found"):
            g.add_edge(_make_edge("a", "missing"))

    def test_get_neighbors_out(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        g.add_entity(_make_entity("b", title="B"))
        g.add_entity(_make_entity("c", title="C"))
        g.add_edge(_make_edge("a", "b"))
        g.add_edge(_make_edge("a", "c", RelationType.REFERENCES))
        out = g.get_neighbors("a", direction="out")
        assert len(out) == 2

    def test_get_neighbors_in(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        g.add_entity(_make_entity("b", title="B"))
        g.add_edge(_make_edge("b", "a"))
        incoming = g.get_neighbors("a", direction="in")
        assert len(incoming) == 1
        assert incoming[0].source_id == "b"

    def test_get_neighbors_by_relation(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        g.add_entity(_make_entity("b", title="B"))
        g.add_entity(_make_entity("c", title="C"))
        g.add_edge(_make_edge("a", "b"))
        g.add_edge(_make_edge("a", "c", RelationType.IMPLEMENTS))
        cites = g.get_neighbors("a", direction="out", relation=RelationType.CITES)
        assert len(cites) == 1

    def test_remove_edge(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        g.add_entity(_make_entity("b", title="B"))
        g.add_edge(_make_edge("a", "b"))
        assert g.remove_edge("a", "b", RelationType.CITES) is True
        assert len(g._edges) == 0
        assert g.remove_edge("a", "b", RelationType.CITES) is False


# ── Search tests ──


class TestSearch:
    def test_basic_search(self):
        g = _populated_graph()
        results = g.search("数字化")
        assert len(results) > 0
        # pol-001 has "数字化转型政策" and "数字化" tag
        ids = [e.id for e, _ in results]
        assert "pol-001" in ids

    def test_search_chinese_policy(self):
        g = _populated_graph()
        results = g.search("卫生健康")
        assert len(results) > 0
        ids = [e.id for e, _ in results]
        assert "pol-001" in ids

    def test_search_no_results(self):
        g = _populated_graph()
        results = g.search("xyznonexistent")
        assert len(results) == 0

    def test_search_respects_top_k(self):
        g = _populated_graph()
        results = g.search("管理", top_k=1)
        assert len(results) <= 1

    def test_search_empty_query(self):
        g = _populated_graph()
        assert g.search("") == []


# ── BFS tests ──


class TestBFS:
    def test_bfs_basic(self):
        g = _populated_graph()
        # BFS from pol-001 should reach reg-001, reg-002 (outgoing)
        distances = g.bfs("pol-001", max_hops=1)
        assert "pol-001" in distances
        assert distances["pol-001"] == 0
        assert "reg-001" in distances
        assert "reg-002" in distances

    def test_bfs_two_hops(self):
        g = _populated_graph()
        # pol-001 → reg-001 → adr-001 (2 hops via implements+cites)
        distances = g.bfs("pol-001", max_hops=2)
        assert "adr-001" in distances

    def test_bfs_nonexistent_start(self):
        g = KnowledgeGraph()
        assert g.bfs("nope") == {}

    def test_bfs_with_relation_filter(self):
        g = _populated_graph()
        distances = g.bfs("pol-001", max_hops=1, relation=RelationType.IMPLEMENTS)
        assert "reg-001" in distances
        # pol-002 supersedes pol-001 (incoming), so not in outgoing IMPLEMENTS
        assert "pol-002" not in distances


# ── Source chain tests ──


class TestSourceChain:
    def test_source_chain_follows_cites(self):
        g = _populated_graph()
        # reg-001 cites adr-001
        chain = g.source_chain("reg-001")
        ids = [e.id for e in chain]
        assert "adr-001" in ids

    def test_source_chain_empty(self):
        g = KnowledgeGraph()
        g.add_entity(_make_entity("a"))
        assert g.source_chain("a") == []


# ── Stats tests ──


class TestStats:
    def test_stats(self):
        g = _populated_graph()
        s = g.stats()
        assert s["total_entities"] == 6
        assert s["total_edges"] == 5
        assert s["entity_types"]["policy"] == 2
        assert s["entity_types"]["regulation"] == 2
        assert s["relation_types"]["cites"] == 1
        assert s["relation_types"]["implements"] == 2

    def test_stats_empty_graph(self):
        g = KnowledgeGraph()
        s = g.stats()
        assert s["total_entities"] == 0
        assert s["total_edges"] == 0
        assert s["avg_out_degree"] == 0.0


# ── Persistence tests ──


class TestPersistence:
    def test_save_and_load(self, tmp_path: Path):
        g = _populated_graph()
        path = tmp_path / "graph.jsonl"
        g.save(path)

        g2 = KnowledgeGraph.load(path)
        assert g2.stats()["total_entities"] == 6
        assert g2.stats()["total_edges"] == 5
        assert g2.get_entity("pol-001") is not None

    def test_load_nonexistent(self, tmp_path: Path):
        g = KnowledgeGraph.load(tmp_path / "missing.jsonl")
        assert g.stats()["total_entities"] == 0

    def test_content_digest_deterministic(self):
        g1 = _populated_graph()
        g2 = _populated_graph()
        assert g1.content_digest() == g2.content_digest()

    def test_content_digest_changes_with_edit(self):
        g = _populated_graph()
        d1 = g.content_digest()
        g.add_entity(_make_entity("new-1", EntityType.POLICY, title="New"))
        d2 = g.content_digest()
        assert d1 != d2


# ── Scale test (5000 nodes, 20000 edges) ──


class TestScale:
    def test_5000_nodes_20000_edges(self):
        """Validate the graph meets BET criteria C1 (≥5000 nodes) and C2 (≥20000 edges)."""
        g = KnowledgeGraph()
        # Create 5000 entities
        for i in range(5000):
            etype = [EntityType.POLICY, EntityType.REGULATION, EntityType.ADR, EntityType.APPROVAL][i % 4]
            g.add_entity(Entity(
                id=f"ent-{i:05d}",
                entity_type=etype,
                title=f"Entity {i} about health policy topic {i % 100}",
                content=f"Content for entity {i} describing regulation detail {i % 50}",
                tags=[f"tag-{i % 20}", f"group-{i % 10}"],
            ))
        # Create 20000 edges (4 per node on average)
        import random
        rng = random.Random(42)  # deterministic
        all_ids = [f"ent-{i:05d}" for i in range(5000)]
        rels = list(RelationType)
        edge_set: set[tuple[str, str, str]] = set()
        while len(edge_set) < 20000:
            src = rng.choice(all_ids)
            tgt = rng.choice(all_ids)
            rel = rng.choice(rels)
            key = (src, tgt, rel.value)
            if src != tgt and key not in edge_set:
                edge_set.add(key)
                g.add_edge(Edge(source_id=src, target_id=tgt, relation=rel))

        s = g.stats()
        assert s["total_entities"] >= 5000, f"C1 FAIL: {s['total_entities']}"
        assert s["total_edges"] >= 20000, f"C2 FAIL: {s['total_edges']}"

        # Verify search still works at scale
        results = g.search("health policy")
        assert len(results) > 0

        # Verify BFS at scale
        distances = g.bfs("ent-00000", max_hops=2)
        assert len(distances) > 1

    def test_save_load_at_scale(self, tmp_path: Path):
        """Verify 5000+ node graph persists correctly."""
        g = KnowledgeGraph()
        for i in range(5000):
            g.add_entity(Entity(
                id=f"e-{i:05d}",
                entity_type=EntityType.POLICY,
                title=f"Node {i}",
                content=f"Content {i}",
            ))
        path = tmp_path / "big-graph.jsonl"
        g.save(path)

        g2 = KnowledgeGraph.load(path)
        assert g2.stats()["total_entities"] == 5000
