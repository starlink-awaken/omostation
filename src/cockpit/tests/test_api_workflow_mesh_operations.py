from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_workflow_mesh_operations


def test_workflow_mesh_operations_api_is_read_only_projection(monkeypatch, tmp_path):
    projection = {
        "schema_version": "workflow-mesh-operations/v1",
        "status": "live",
        "summary": {"run_count": 2, "active_runs": 1},
        "review_queue": [],
        "consumption": {"status": "not_observed", "consumed_runs": 0},
    }
    calls: list[tuple[object, str | None]] = []

    def fake_build(omo_dir, *, scene_id=None):
        calls.append((omo_dir, scene_id))
        return projection

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_operations_snapshot", fake_build)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)
    response = TestClient(app).get("/api/workflow-mesh/operations?scene_id=engineering-delivery")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "live", "operations": projection}
    assert calls == [(tmp_path / ".omo", "engineering-delivery")]


def test_workflow_mesh_operations_api_degrades_without_omo(monkeypatch):
    monkeypatch.setattr(api_workflow_mesh_operations, "build_operations_snapshot", None)
    monkeypatch.setattr(api_workflow_mesh_operations, "_OMO_IMPORT_ERROR", ImportError("missing omo"))

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)
    response = TestClient(app).get("/api/workflow-mesh/operations")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["operations"]["status"] == "unavailable"
