"""Tests for cockpit.web.api_metaos — 22% coverage file."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from cockpit.web.api_metaos import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestMetaosPlan:
    def test_plan_ok(self, client):
        mock_wf = MagicMock()
        mock_wf.workflow_id = "wf-123"
        mock_wf.nodes = {
            "n1": MagicMock(task_type="search", depends_on=[]),
            "n2": MagicMock(task_type="analyze", depends_on=["n1"]),
        }
        mock_engine = MagicMock()
        mock_engine.register_h.return_value = "token-123"

        with (
            patch("cockpit.web.api_metaos._get_engine", return_value=mock_engine),
            patch("cockpit.web.api_metaos.WorkflowPlanner") as mock_planner,
        ):
            mock_planner.return_value.plan.return_value = mock_wf
            resp = client.post("/api/metaos/plan", json={"task": "analyze codebase"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["workflow_id"] == "wf-123"
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

    def test_plan_missing_task(self, client):
        resp = client.post("/api/metaos/plan", json={})
        assert resp.status_code == 400
        assert resp.json()["error"] == "task is required"

    def test_plan_error(self, client):
        with patch("cockpit.web.api_metaos._get_engine", side_effect=Exception("engine fail")):
            resp = client.post("/api/metaos/plan", json={"task": "test"})
        assert resp.status_code == 500


class TestMetaosExecute:
    def test_execute_ok(self, client):
        resp = client.post("/api/metaos/execute", json={"task": "run tests"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert "background" in resp.json()["msg"]

    def test_execute_missing_task(self, client):
        resp = client.post("/api/metaos/execute", json={})
        assert resp.status_code == 400


class TestMetaosWorkflows:
    def test_list_workflows(self, client):
        mock_store = MagicMock()
        mock_store.list_workflows.return_value = [
            {"id": "wf1", "status": "completed"},
            {"id": "wf2", "status": "running"},
        ]
        with patch("cockpit.web.api_metaos.WorkflowStore", return_value=mock_store):
            resp = client.get("/api/metaos/workflows")
        assert resp.status_code == 200
        assert len(resp.json()["workflows"]) == 2

    def test_workflow_detail(self, client):
        mock_store = MagicMock()
        mock_store.get_workflow.return_value = {
            "id": "wf1",
            "nodes": [
                {"id": "n1", "type": "search", "status": "completed", "output": "result"},
            ],
        }
        with patch("cockpit.web.api_metaos.WorkflowStore", return_value=mock_store):
            resp = client.get("/api/metaos/workflows/wf1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow"]["nodes"][0]["task_type"] == "search"

    def test_workflow_detail_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_workflow.return_value = None
        with patch("cockpit.web.api_metaos.WorkflowStore", return_value=mock_store):
            resp = client.get("/api/metaos/workflows/nonexistent")
        assert resp.status_code == 404

    def test_workflow_approve(self, client):
        mock_store = MagicMock()
        mock_store.get_workflow.return_value = {
            "id": "wf1",
            "nodes": [
                {"id": "n1", "type": "search", "status": "awaiting_approval"},
            ],
        }
        mock_conn = MagicMock()
        mock_store._conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_store._conn.return_value.__exit__ = MagicMock(return_value=False)
        with patch("cockpit.web.api_metaos.WorkflowStore", return_value=mock_store):
            resp = client.post("/api/metaos/workflows/wf1/approve")
        assert resp.status_code == 200
        assert "approved" in resp.json()["msg"]

    def test_workflow_approve_no_awaiting(self, client):
        mock_store = MagicMock()
        mock_store.get_workflow.return_value = {
            "id": "wf1",
            "nodes": [
                {"id": "n1", "type": "search", "status": "completed"},
            ],
        }
        with patch("cockpit.web.api_metaos.WorkflowStore", return_value=mock_store):
            resp = client.post("/api/metaos/workflows/wf1/approve")
        assert resp.status_code == 400
