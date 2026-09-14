"""Phase 7: Neo4j recall backend closes write→search loop."""

from __future__ import annotations

from mos.neo4j_writer import FakeNeo4jDriver, Neo4jFactWriter, Neo4jSearchBackend
from mos.routing import backends_for_intent
from mos.service import MemoryOS


def test_temporal_fact_routes_prefer_neo4j():
    names = backends_for_intent("temporal_fact")
    assert names[0] == "neo4j"
    assert "temporal" in names


def test_neo4j_search_backend_fixed_hits():
    backend = Neo4jSearchBackend(
        fixed_hits=[
            {
                "id": "f1",
                "title": "Alice works_at Acme",
                "snippet": "Alice works at Acme",
                "subject": "Alice",
                "predicate": "works_at",
                "object": "Acme",
            }
        ]
    )
    hits = backend.search("Alice", limit=5)
    assert len(hits) == 1
    assert hits[0]["backend"] == "neo4j"


def test_write_then_recall_via_fake_neo4j(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("MOS_TEMPORAL", "1")
    fake = FakeNeo4jDriver()
    writer = Neo4jFactWriter(driver_factory=lambda: fake)
    mos = MemoryOS(neo4j=writer, enforce_rbac=True)
    # ensure search uses same writer
    mos.register_search_backend("neo4j", Neo4jSearchBackend(writer=writer))

    w = mos.write(
        {
            "type": "semantic",
            "content": "Carol founded NeoSoft in 2024",
            "subject": "Carol",
            "predicate": "founded",
            "object": "NeoSoft",
            "confidence": 0.95,
            "principal_id": "u1",
        }
    )
    assert w.ok
    assert w.neo4j and w.neo4j.get("ok")
    assert any(f.get("subject") == "Carol" for f in fake.facts)

    rec = mos.recall("Carol founded", intent="temporal_fact", limit=10)
    assert rec.count >= 1
    assert rec.backend_status.get("neo4j") == "ok"
    neo_hits = [h for h in rec.hits if h.get("backend") == "neo4j" or "neo4j" in (h.get("backends") or [])]
    # RRF may merge; at least one hit mentions Carol
    blob = " ".join(str(h.get("snippet") or h.get("title") or "") for h in rec.hits).lower()
    assert "carol" in blob or neo_hits


def test_recall_skips_neo4j_when_uri_unset(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    mos = MemoryOS(enforce_rbac=True)
    rec = mos.recall("anything temporal valid_from", intent="temporal_fact")
    assert "neo4j" not in rec.backend_status


def test_status_reports_neo4j_recall(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    st = MemoryOS(enforce_rbac=True).status()
    assert st["version"] == "0.10.0"
    assert st.get("neo4j_as_of") is True
    assert st["neo4j_recall"] is False
