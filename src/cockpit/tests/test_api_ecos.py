"""Tests for cockpit.web.api_ecos — lowest coverage file (18%)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from cockpit.web.api_ecos import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestEcosStatus:
    def test_status_ok(self, client, tmp_path, monkeypatch):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ego_dir = repo_root / "ecos" / "__init__.py"
        ego_dir.mkdir(parents=True, exist_ok=True)
        (repo_root / ".git").mkdir()

        monkeypatch.setattr("cockpit.web.api_ecos._REPO_ROOT", repo_root)

        resp = client.get("/api/ecos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "ecos-dashboard"
        assert data["status"] in ("converged", "degraded")

    def test_status_degraded_when_no_files(self, client, tmp_path, monkeypatch):
        repo_root = tmp_path / "empty_repo"
        repo_root.mkdir()
        monkeypatch.setattr("cockpit.web.api_ecos._REPO_ROOT", repo_root)

        resp = client.get("/api/ecos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "converged"


class TestEcosHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/ecos/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "ecos-dashboard-converged"


class TestWorkflowEndpoints:
    def test_list_workflows(self, client):
        with patch("cockpit.adapters.ecos.list_workflows", return_value=[]):
            resp = client.get("/api/ecos/workflow/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflows"] == []

    def test_list_workflows_with_data(self, client):
        mock_workflows = [{"id": "wf1", "name": "Test Workflow"}]
        with patch("cockpit.adapters.ecos.list_workflows", return_value=mock_workflows):
            resp = client.get("/api/ecos/workflow/list")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_workflows_error(self, client):
        with patch("cockpit.adapters.ecos.list_workflows", side_effect=Exception("boom")):
            resp = client.get("/api/ecos/workflow/list")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_run_workflow(self, client):
        mock_result = {"workflow": "test", "passed": 3, "failed": 0}
        with patch("cockpit.adapters.ecos.execute_m1_workflow", return_value=mock_result):
            resp = client.post("/api/ecos/workflow/run?name=test&dry_run=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] == 3

    def test_describe_workflow(self, client):
        mock_wf = {"name": "test", "steps": ["a", "b"]}
        with patch("cockpit.adapters.ecos.load_workflow", return_value=mock_wf):
            resp = client.get("/api/ecos/workflow/describe/test")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test"

    def test_describe_workflow_not_found(self, client):
        with patch("cockpit.adapters.ecos.load_workflow", return_value=None):
            resp = client.get("/api/ecos/workflow/describe/nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_list_backends(self, client):
        with patch("cockpit.adapters.ecos.list_backends", return_value=["shell"]):
            resp = client.get("/api/ecos/workflow/backends")
        assert resp.status_code == 200
        assert resp.json()["backends"] == ["shell"]

    def test_list_actions(self, client):
        with patch("cockpit.adapters.ecos.list_actions", return_value=["grep", "sed"]):
            resp = client.get("/api/ecos/workflow/actions")
        assert resp.status_code == 200
        assert len(resp.json()["actions"]) == 2

    def test_validate_workflow(self, client):
        mock_wf = {"name": "test"}
        with (
            patch("cockpit.adapters.ecos.load_workflow", return_value=mock_wf),
            patch("cockpit.adapters.ecos.validate_workflow", return_value=[]),
        ):
            resp = client.get("/api/ecos/workflow/validate/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    def test_workflow_logs(self, client):
        mock_runs = [{"id": "r1", "status": "ok"}, {"id": "r2", "status": "failed"}]
        with patch("cockpit.adapters.ecos.load_all_workflow_runs", return_value=mock_runs):
            resp = client.get("/api/ecos/workflow/logs?recent=10")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_workflow_logs_filtered(self, client):
        mock_runs = [
            {"id": "r1", "status": "ok"},
            {"id": "r2", "status": "ok"},
            {"id": "r3", "status": "failed"},
        ]
        with patch("cockpit.adapters.ecos.load_all_workflow_runs", return_value=mock_runs):
            resp = client.get("/api/ecos/workflow/logs?status=ok")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_test_workflow(self, client):
        mock_result = {"workflow": "test", "tests_passed": 5}
        with patch("cockpit.adapters.ecos.test_workflow", return_value=mock_result):
            resp = client.post("/api/ecos/workflow/test?name=test")
        assert resp.status_code == 200
        assert resp.json()["tests_passed"] == 5


class TestSkills:
    def test_list_skills_empty(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        resp = client.get("/api/ecos/skills")
        assert resp.status_code == 200

    def test_list_skills_with_workspace_skills(self, client, tmp_path, monkeypatch):
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: My Skill\n---\nContent")

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        resp = client.get("/api/ecos/skills")
        assert resp.status_code == 200
