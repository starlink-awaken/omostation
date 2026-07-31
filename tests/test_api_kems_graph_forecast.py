from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


def client():
    app = FastAPI()
    app.include_router(api_kems.router)
    return TestClient(app)


def seed_graph(monkeypatch, tmp_path):
    from kos.kems import DocumentVersion, EvidenceSpan, GraphEntity, GraphRelation, GraphStore

    monkeypatch.setenv("KEMS_GRAPH_DB", str(tmp_path / "graph.sqlite"))
    store = GraphStore(tmp_path / "graph.sqlite")
    store.put_document_version(
        DocumentVersion("doc-1", "v1", "a" * 64, "official_work", "private source", run_id="run-1")
    )
    store.add_evidence(EvidenceSpan("ev-1", "doc-1", "v1", "page=1", "private source", "ocr", 0.9, "run-1"))
    store.add_entity(GraphEntity("ent-1", "policy", "政策 A", "doc-1", "v1", "ev-1", 0.9, created_by_run="run-1"))
    store.add_entity(GraphEntity("ent-2", "org", "单位 B", "doc-1", "v1", "ev-1", 0.9, created_by_run="run-1"))
    store.add_relation(
        GraphRelation("rel-1", "ent-1", "issued_by", "ent-2", "doc-1", "v1", ("ev-1",), 0.9, created_by_run="run-1")
    )


def test_graph_api_is_evidence_bound_and_supports_rollback(monkeypatch, tmp_path):
    seed_graph(monkeypatch, tmp_path)
    response = client().get("/api/kems/graph/entities", params={"q": "政策"})
    assert response.status_code == 200
    assert response.json()["items"][0]["entity_id"] == "ent-1"
    assert "text" not in response.json()["items"][0]
    assert client().get("/api/kems/graph/entities/ent-1/neighbors").json()["count"] == 1
    reviewed = client().post(
        "/api/kems/graph/entities/ent-1/review",
        json={"decision": "human_verified", "reviewer": "alice", "reason": "checked", "decision_id": "d-1"},
    )
    assert reviewed.status_code == 200
    rolled_back = client().post(
        "/api/kems/graph/runs/run-1/rollback",
        json={"reviewer": "alice", "reason": "source withdrawn", "decision_id": "d-2"},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["counts"]["relations"] == 1


def test_shadow_forecast_api_persists_and_evaluates(monkeypatch, tmp_path):
    monkeypatch.setenv("KEMS_FORECAST_DB", str(tmp_path / "forecast.sqlite"))
    result = client().post(
        "/api/kems/forecast/shadow",
        json={
            "forecast_id": "f-1",
            "series_id": "queue",
            "source_run_id": "run-1",
            "values": [10, 12, 14],
            "horizon": 2,
        },
    )
    assert result.status_code == 200
    assert result.json()["forecast"]["mode"] == "shadow"
    assert client().get("/api/kems/forecast/f-1").json()["predictions"] == [12.0, 12.0]
    evaluation = client().post(
        "/api/kems/forecast/f-1/evaluation",
        json={"evaluation_id": "e-1", "actual": [15, 16]},
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["evaluation"]["mode"] == "shadow"
