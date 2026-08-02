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


def test_outcome_feedback_api_forwards_safe_payload_and_actor(monkeypatch, tmp_path):
    captured: list[tuple[object, dict, str]] = []

    def fake_record(omo_dir, payload, *, actor):
        captured.append((omo_dir, payload, actor))
        return {
            "status": "recorded",
            "feedback": {
                "schema": "outcome-feedback/v1",
                "feedback_id": "outcome-feedback:test",
            },
        }

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_outcome_feedback", fake_record)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)
    response = TestClient(app).post(
        "/api/workflow-mesh/outcome-feedback",
        json={
            "workflow_run_id": "run-1",
            "outcome_id": "outcome-1",
            "scene_binding": {
                "scene_id": "engineering-delivery",
                "journey_id": "intent-to-evidence",
                "outcome_metric": "verified_delivery_lead_time",
            },
            "consumption_state": "reviewed",
            "consumer_ref": "operator://redacted/reviewer-1",
            "actor_ref": "operator://redacted/reviewer-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured[0][0] == tmp_path / ".omo"
    assert captured[0][1]["outcome_id"] == "outcome-1"
    assert "actor_ref" not in captured[0][1]
    assert captured[0][2] == "operator://redacted/reviewer-1"


def test_outcome_feedback_api_returns_explicit_invalid_status(monkeypatch, tmp_path):
    def fail_record(_omo_dir, _payload, *, actor):
        raise ValueError("feedback scene_binding does not match WorkflowRun")

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_outcome_feedback", fail_record)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)
    response = TestClient(app).post(
        "/api/workflow-mesh/outcome-feedback",
        json={"workflow_run_id": "run-1"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"] == "outcome_feedback_invalid"


def test_outcome_feedback_api_returns_unavailable_on_persistence_error(monkeypatch, tmp_path):
    def fail_record(_omo_dir, _payload, *, actor):
        raise OSError("disk unavailable")

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_outcome_feedback", fail_record)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)
    response = TestClient(app).post(
        "/api/workflow-mesh/outcome-feedback",
        json={"workflow_run_id": "run-1"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "unavailable"
    assert response.json()["error"] == "outcome_feedback_unavailable"
