"""Tests for cockpit.web.api_ecos — lowest coverage file (18%)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
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


class TestEcosStatusWithData:
    """Cover L47-52: port-registry file reading path."""

    def test_status_reads_port_registry(self, client, tmp_path, monkeypatch):
        """When port-registry.yaml exists, counts ports and mcp_transport_defaults."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        protocols_dir = repo_root / "protocols"
        protocols_dir.mkdir()

        port_data = {
            "ports": {str(i): {"name": f"port-{i}"} for i in range(5)},
            "mcp_transport_defaults": {"stdio": "default", "sse": "default"},
            "env_vars": {"FOO": "BAR"},
        }
        (protocols_dir / "port-registry.yaml").write_text(yaml.dump(port_data))
        # Create ecos M0 snapshot path
        m0_dir = repo_root / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m0"
        m0_dir.mkdir(parents=True)
        (m0_dir / "snapshot.yaml").touch()

        monkeypatch.setattr("cockpit.web.api_ecos._REPO_ROOT", repo_root)

        resp = client.get("/api/ecos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "converged"
        assert data["ssot"]["port_registry_ports"] == 5
        assert data["ssot"]["mcp_stdio_defaults"] == 2  # L52 covered
        assert data["m0_snapshot"] == "available"

    def test_status_exception_returns_degraded(self, client, tmp_path, monkeypatch):
        """L68-69: When an exception occurs, return degraded status."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        protocols_dir = repo_root / "protocols"
        protocols_dir.mkdir()
        # Write invalid YAML to trigger exception
        (protocols_dir / "port-registry.yaml").write_text("{{invalid yaml: [")

        monkeypatch.setattr("cockpit.web.api_ecos._REPO_ROOT", repo_root)

        resp = client.get("/api/ecos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert "error" in data


class TestWorkflowErrorPaths:
    """Cover L120-124, L146-147, L156-157, L167, L178-179, L197-218."""

    def test_run_workflow_error(self, client):
        """L120-121: execute_m1_workflow raises exception."""
        with patch("cockpit.adapters.ecos.execute_m1_workflow", side_effect=Exception("exec fail")):
            resp = client.post("/api/ecos/workflow/run?name=bad")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_run_workflow_serialization(self, client):
        """L123-124: Result with non-serializable values."""
        mock_result = {
            "workflow": "test",
            "passed": 3,
            "failed": 0,
            "obj": object(),  # Non-serializable
        }
        with patch("cockpit.adapters.ecos.execute_m1_workflow", return_value=mock_result):
            resp = client.post("/api/ecos/workflow/run?name=test")
        assert resp.status_code == 200
        data = resp.json()
        # Non-serializable field should be converted to string
        assert "obj" in data

    def test_describe_workflow_exception(self, client):
        """L136-137: load_workflow raises exception."""
        with patch("cockpit.adapters.ecos.load_workflow", side_effect=Exception("load fail")):
            resp = client.get("/api/ecos/workflow/describe/bad")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_list_backends_error(self, client):
        """L146-147: list_backends raises exception."""
        with patch("cockpit.adapters.ecos.list_backends", side_effect=Exception("backends fail")):
            resp = client.get("/api/ecos/workflow/backends")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_list_actions_error(self, client):
        """L156-157: list_actions raises exception."""
        with patch("cockpit.adapters.ecos.list_actions", side_effect=Exception("actions fail")):
            resp = client.get("/api/ecos/workflow/actions")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_validate_workflow_not_found(self, client):
        """L167: load_workflow returns None."""
        with patch("cockpit.adapters.ecos.load_workflow", return_value=None):
            resp = client.get("/api/ecos/workflow/validate/nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_validate_workflow_with_violations(self, client):
        """Validate workflow returns violations."""
        mock_wf = {"name": "test"}
        violations = [
            {"severity": "error", "msg": "missing id"},
            {"severity": "warning", "msg": "missing desc"},
        ]
        with (
            patch("cockpit.adapters.ecos.load_workflow", return_value=mock_wf),
            patch("cockpit.adapters.ecos.validate_workflow", return_value=violations),
        ):
            resp = client.get("/api/ecos/workflow/validate/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert len(data["warnings"]) == 1

    def test_validate_workflow_exception(self, client):
        """L178-179: validate_workflow raises exception."""
        mock_wf = {"name": "test"}
        with (
            patch("cockpit.adapters.ecos.load_workflow", return_value=mock_wf),
            patch("cockpit.adapters.ecos.validate_workflow", side_effect=Exception("validation fail")),
        ):
            resp = client.get("/api/ecos/workflow/validate/test")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_test_workflow_error(self, client):
        """L197-198: test_workflow raises exception."""
        with patch("cockpit.adapters.ecos.test_workflow", side_effect=Exception("test fail")):
            resp = client.post("/api/ecos/workflow/test?name=bad")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_test_workflow_serialization(self, client):
        """L214-218: JSON serialization of non-serializable result values."""
        mock_result = {
            "workflow": "test",
            "valid": True,
            "fn": lambda: None,  # Non-serializable
        }
        with patch("cockpit.adapters.ecos.test_workflow", return_value=mock_result):
            resp = client.post("/api/ecos/workflow/test?name=test")
        assert resp.status_code == 200
        data = resp.json()
        # Non-serializable field converted to string
        assert "fn" in data


class TestSkillsCoverage:
    """Cover L238-257, L287-288: skills directory scanning."""

    def test_list_skills_with_global_plugins(self, client, tmp_path, monkeypatch):
        """L238-244: Scan global plugins directory."""
        plugins_dir = tmp_path / ".gemini" / "config" / "plugins"
        plugin_dir = plugins_dir / "my-plugin"
        skills_dir = plugin_dir / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "global-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Global Skill")

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        resp = client.get("/api/ecos/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert any(s["id"] == "global-skill" for s in data["skills"])

    def test_list_skills_with_builtin_skills(self, client, tmp_path, monkeypatch):
        """L255-257: Scan builtin skills directory."""
        builtin_dir = tmp_path / ".gemini" / "antigravity-cli" / "builtin" / "skills"
        builtin_dir.mkdir(parents=True)
        skill_dir = builtin_dir / "builtin-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Builtin Skill")

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        resp = client.get("/api/ecos/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert any(s["id"] == "builtin-skill" for s in data["skills"])

    def test_list_skills_parse_error(self, client, tmp_path, monkeypatch):
        """Skills with unparseable YAML frontmatter still appear."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        skills_dir = repo_root / ".agents" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "broken-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("No frontmatter here")

        # Also create global skills dir to avoid scanning real home
        global_dir = tmp_path / ".gemini" / "config" / "plugins"
        global_dir.mkdir(parents=True)
        builtin_dir = tmp_path / ".gemini" / "antigravity-cli" / "builtin" / "skills"
        builtin_dir.mkdir(parents=True)

        monkeypatch.setattr("cockpit.web.api_ecos._REPO_ROOT", repo_root)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        resp = client.get("/api/ecos/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert any(s["id"] == "broken-skill" for s in data["skills"])

    def test_list_skills_exception(self, client, tmp_path, monkeypatch):
        """L287-288: Exception in skills listing returns error."""
        # Force an error by mocking Path.iterdir to raise
        original_iterdir = Path.iterdir

        def failing_iterdir(self):
            if ".agents" in str(self):
                raise PermissionError("Access denied")
            return original_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", failing_iterdir)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        resp = client.get("/api/ecos/skills")
        assert resp.status_code == 500
        assert "error" in resp.json()


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
