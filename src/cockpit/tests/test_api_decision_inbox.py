"""Tests for Decision Inbox API endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_decision_inbox


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_decision_inbox.router)
    return app


def test_decision_inbox_summary_returns_ok(monkeypatch, tmp_path):
    """GET /api/decision-inbox/summary should return ok with zero counts."""
    monkeypatch.setattr(api_decision_inbox, "_REPO_ROOT", tmp_path)

    response = TestClient(_app()).get("/api/decision-inbox/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["summary"]["scene_count"] == 0
    assert data["summary"]["total_intents"] == 0
    assert data["summary"]["pending_intents"] == 0


def test_decision_inbox_create_and_list_scene(monkeypatch, tmp_path):
    """POST /api/decision-inbox/scenes then GET /api/decision-inbox/scenes."""
    monkeypatch.setattr(api_decision_inbox, "_REPO_ROOT", tmp_path)

    client = TestClient(_app())

    # Create scene
    response = client.post("/api/decision-inbox/scenes", json={
        "name": "测试场景",
        "description": "一个测试场景",
        "priority": "P1",
    })
    assert response.status_code == 200
    create_data = response.json()
    assert create_data["ok"] is True
    scene_id = create_data["scene"]["id"]
    assert scene_id.startswith("scene-")

    # List scenes
    response = client.get("/api/decision-inbox/scenes")
    assert response.status_code == 200
    list_data = response.json()
    assert list_data["ok"] is True
    assert len(list_data["scenes"]) == 1
    assert list_data["scenes"][0]["id"] == scene_id


def test_decision_inbox_scene_create_journey_and_add_intent(monkeypatch, tmp_path):
    """Full lifecycle: create scene → create journey → add intent → list intents."""
    monkeypatch.setattr(api_decision_inbox, "_REPO_ROOT", tmp_path)

    client = TestClient(_app())

    # Create scene
    resp = client.post("/api/decision-inbox/scenes", json={"name": "决策收件箱", "description": "测试"})
    assert resp.status_code == 200
    scene_id = resp.json()["scene"]["id"]

    # Create journey
    resp = client.post(f"/api/decision-inbox/scenes/{scene_id}/journeys", json={"name": "邮件处理"})
    assert resp.status_code == 200
    resp.json()["journey"]["id"]

    # Add intent
    resp = client.post(f"/api/decision-inbox/scenes/{scene_id}/intents", json={
        "source": "email",
        "raw_content": "需要处理客户反馈的紧急问题",
        "priority": "P0",
    })
    assert resp.status_code == 200
    intent_data = resp.json()
    assert intent_data["ok"] is True
    intent_id = intent_data["intent"]["id"]

    # List intents
    resp = client.get(f"/api/decision-inbox/scenes/{scene_id}/intents")
    assert resp.status_code == 200
    intents = resp.json()["intents"]
    assert len(intents) == 1
    assert intents[0]["id"] == intent_id
    assert intents[0]["status"] == "pending"

    # Update intent status
    resp = client.patch(f"/api/decision-inbox/intents/{intent_id}", json={
        "status": "approved",
    })
    assert resp.status_code == 200
    updated = resp.json()["intent"]
    assert updated["status"] == "approved"

    # Verify summary reflects the change
    resp = client.get("/api/decision-inbox/summary")
    summary = resp.json()["summary"]
    assert summary["pending_intents"] == 0
    assert summary["total_intents"] == 1


def test_decision_inbox_get_scene_detail(monkeypatch, tmp_path):
    """GET /api/decision-inbox/scenes/{id} returns scene with journeys and intents."""
    monkeypatch.setattr(api_decision_inbox, "_REPO_ROOT", tmp_path)

    client = TestClient(_app())

    # Create scene
    resp = client.post("/api/decision-inbox/scenes", json={"name": "详情测试", "description": ""})
    scene_id = resp.json()["scene"]["id"]

    # Create journey + intent
    client.post(f"/api/decision-inbox/scenes/{scene_id}/journeys", json={"name": "测试流程"})
    client.post(f"/api/decision-inbox/scenes/{scene_id}/intents", json={
        "source": "manual", "raw_content": "测试意图内容",
    })

    # Get scene detail
    resp = client.get(f"/api/decision-inbox/scenes/{scene_id}")
    assert resp.status_code == 200
    scene = resp.json()["scene"]
    assert scene["name"] == "详情测试"
    assert len(scene["journeys"]) == 1
    assert len(scene["journeys"][0]["intents"]) == 1


def test_decision_inbox_unavailable_when_no_engine(monkeypatch, tmp_path):
    """When engine is unavailable, return appropriate error."""
    monkeypatch.setattr(api_decision_inbox, "_engine_available", False)

    resp = TestClient(_app()).get("/api/decision-inbox/summary")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert resp.json()["status"] == "unavailable"
