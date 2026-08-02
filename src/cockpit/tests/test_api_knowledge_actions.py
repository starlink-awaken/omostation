from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_knowledge_actions


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_knowledge_actions.router)
    return app


def test_knowledge_action_operations_is_log_derived(monkeypatch, tmp_path):
    projection = {"schema_version": "knowledge-action-operations/v1", "status": "live", "summary": {"task_count": 1}}
    calls = []

    def fake_build(omo_dir, *, scene_id=None):
        calls.append((omo_dir, scene_id))
        return projection

    monkeypatch.setattr(api_knowledge_actions, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_knowledge_actions, "build_knowledge_action_snapshot", fake_build)
    response = TestClient(_app()).get("/api/knowledge/action-operations?scene_id=engineering-delivery")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "live", "operations": projection}
    assert calls == [(tmp_path / ".omo", "engineering-delivery")]


def test_knowledge_action_receipt_removes_actor_ref(monkeypatch, tmp_path):
    captured = []

    def fake_record(omo_dir, payload, *, actor):
        captured.append((omo_dir, payload, actor))
        return {"status": "recorded", "action": {"action_id": "knowledge-action:test"}}

    monkeypatch.setattr(api_knowledge_actions, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_knowledge_actions, "record_knowledge_action", fake_record)
    response = TestClient(_app()).post(
        "/api/knowledge/action-receipt",
        json={"action_kind": "retrieved", "query": "治理", "knowledge_refs": [{"ref": "kos:1"}], "actor_ref": "cockpit-ui://test"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"
    assert captured == [(tmp_path / ".omo", {"action_kind": "retrieved", "query": "治理", "knowledge_refs": [{"ref": "kos:1"}]}, "cockpit-ui://test")]


def test_knowledge_action_receipt_reports_invalid_payload(monkeypatch):
    def fail_record(*_args, **_kwargs):
        raise ValueError("scene binding is required")

    monkeypatch.setattr(api_knowledge_actions, "record_knowledge_action", fail_record)
    response = TestClient(_app()).post("/api/knowledge/action-receipt", json={"action_kind": "task_created"})

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert response.json()["error"] == "knowledge_action_invalid"
