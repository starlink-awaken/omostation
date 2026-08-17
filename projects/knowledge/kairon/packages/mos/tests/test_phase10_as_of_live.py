"""Phase 10: Neo4j as_of bi-temporal + live KOS/gbrain backends."""

from __future__ import annotations

from mos.adapters.live_backends import (
    LiveGbrainSearchBackend,
    LiveKosSearchBackend,
    gbrain_put_page,
    live_gbrain_enabled,
    live_kos_enabled,
)
from mos.neo4j_writer import FakeNeo4jDriver, Neo4jFactWriter, Neo4jSearchBackend
from mos.service import MemoryOS


def test_neo4j_as_of_excludes_future_and_expired(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    fake = FakeNeo4jDriver()
    writer = Neo4jFactWriter(driver_factory=lambda: fake)
    # direct upserts via writer
    writer.upsert_fact(
        {
            "id": "f-past",
            "subject": "Alice",
            "predicate": "worked_at",
            "object": "OldCo",
            "content": "Alice worked at OldCo",
            "temporal": {
                "valid_from": "2020-01-01T00:00:00Z",
                "valid_to": "2022-01-01T00:00:00Z",
            },
            "scope": {},
        }
    )
    writer.upsert_fact(
        {
            "id": "f-now",
            "subject": "Alice",
            "predicate": "works_at",
            "object": "NewCo",
            "content": "Alice works at NewCo",
            "temporal": {"valid_from": "2022-01-01T00:00:00Z", "valid_to": None},
            "scope": {},
        }
    )
    # current-state: only f-now (f-past has valid_to in past but not invalidated —
    # current filter uses invalidated_at only; both may appear unless valid_to checked.
    # With as_of null, FakeNeo4j only skips invalidated_at — both present if not invalidated.
    # as_of mid-2021 → only f-past
    hits_2021 = writer.search_facts("Alice", limit=10, as_of="2021-06-01T00:00:00Z")
    ids_2021 = {h["id"] for h in hits_2021}
    assert "f-past" in ids_2021
    assert "f-now" not in ids_2021
    # as_of 2023 → only f-now
    hits_2023 = writer.search_facts("Alice", limit=10, as_of="2023-01-01T00:00:00Z")
    ids_2023 = {h["id"] for h in hits_2023}
    assert "f-now" in ids_2023
    assert "f-past" not in ids_2023


def test_neo4j_as_of_excludes_invalidated_before_point(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    fake = FakeNeo4jDriver()
    writer = Neo4jFactWriter(driver_factory=lambda: fake)
    writer.upsert_fact(
        {
            "id": "f-inv",
            "subject": "Bob",
            "predicate": "likes",
            "object": "tea",
            "content": "Bob likes tea",
            "temporal": {"valid_from": "2020-01-01T00:00:00Z"},
            "scope": {},
        }
    )
    writer.invalidate("f-inv", "2022-06-01T00:00:00Z")
    # before invalidate → visible
    hits_before = writer.search_facts("Bob", as_of="2021-01-01T00:00:00Z")
    assert any(h["id"] == "f-inv" for h in hits_before)
    # after invalidate → hidden
    hits_after = writer.search_facts("Bob", as_of="2023-01-01T00:00:00Z")
    assert not any(h["id"] == "f-inv" for h in hits_after)
    # current-state (no as_of) → hidden
    hits_cur = writer.search_facts("Bob")
    assert not any(h["id"] == "f-inv" for h in hits_cur)


def test_recall_passes_as_of_to_neo4j(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("MOS_TEMPORAL", "1")
    fake = FakeNeo4jDriver()
    writer = Neo4jFactWriter(driver_factory=lambda: fake)
    mos = MemoryOS(neo4j=writer, enforce_rbac=True)
    mos.register_search_backend("neo4j", Neo4jSearchBackend(writer=writer))
    mos.write(
        {
            "type": "semantic",
            "content": "Dana joined Acme",
            "subject": "Dana",
            "predicate": "joined",
            "object": "Acme",
            "valid_from": "2024-01-01T00:00:00Z",
            "confidence": 0.9,
        }
    )
    rec = mos.recall("Dana", intent="temporal_fact", as_of="2024-06-01T00:00:00Z", limit=5)
    assert rec.backend_status.get("neo4j") == "ok"
    # search call recorded with as_of
    search_calls = [c for c in fake.calls if "RETURN" in (c.get("query") or "")]
    assert search_calls
    assert search_calls[-1]["parameters"].get("as_of") == "2024-06-01T00:00:00Z"


def test_live_kos_backend_injectable(monkeypatch):
    monkeypatch.setenv("MOS_LIVE_KOS", "1")
    assert live_kos_enabled() is True

    def fake_get(url: str, params: dict[str, str]):
        return {"results": [{"id": "kos-1", "title": "KOS doc", "snippet": f"hit for {params.get('q')}", "score": 0.9}]}

    be = LiveKosSearchBackend(http_get=fake_get)
    hits = be.search("memory os", limit=5)
    assert len(hits) == 1
    assert hits[0]["backend"] == "kos"
    assert hits[0]["live"] is True
    assert "memory" in hits[0]["snippet"]


def test_live_gbrain_backend_injectable(monkeypatch):
    monkeypatch.setenv("MOS_LIVE_GBRAIN", "1")
    assert live_gbrain_enabled() is True

    def fake_run(cmd: list[str]) -> str:
        assert "search" in cmd or "query" in cmd
        return '[{"id":"gb-1","title":"Gbrain page","snippet":"live gbrain hit"}]'

    be = LiveGbrainSearchBackend(run_cmd=fake_run)
    hits = be.search("test", limit=3)
    assert len(hits) == 1
    assert hits[0]["id"] == "gb-1"
    assert hits[0]["live"] is True


def test_gbrain_put_gated(monkeypatch):
    monkeypatch.delenv("MOS_LIVE_GBRAIN_WRITE", raising=False)
    r = gbrain_put_page("mos/test", "hello")
    assert r.get("skipped") is True

    monkeypatch.setenv("MOS_LIVE_GBRAIN_WRITE", "1")

    def fake_run(cmd: list[str]):
        assert "put" in cmd
        return 0, "ok", ""

    r2 = gbrain_put_page("mos/test", "hello", run_cmd=fake_run)
    assert r2.get("ok") is True


def test_status_reports_live_and_as_of(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.setenv("MOS_LIVE_KOS", "0")
    monkeypatch.setenv("MOS_LIVE_GBRAIN", "0")
    st = MemoryOS(enforce_rbac=True).status()
    assert st["version"] == "0.10.0"
    assert st["neo4j_as_of"] is True
    assert "kos_gbrain_live" in st["adapters"]
