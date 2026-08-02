"""Tests for /api/omos/violations + /api/omos/fix-drift + /api/omos/circuit-break + /api/omos/budget."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


class TestOmosViolations:
    """Cover api_omos.py:605-672 (violations endpoint)."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_violations_no_gatekeeper(self, client, tmp_path, monkeypatch):
        """When gatekeeper.py is missing, returns error."""
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        # Reset cache so each test is fresh
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", None)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", 0.0)

        resp = client.get("/api/omos/violations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "gatekeeper" in data["error"].lower()

    def test_violations_cache_hit(self, client, tmp_path, monkeypatch):
        """Cached result is returned when TTL has not expired."""
        cached = {"status": "ok", "passed": True, "violations": []}
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", cached)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", 9999999999.0)

        resp = client.get("/api/omos/violations")
        assert resp.status_code == 200
        data = resp.json()
        assert data == cached

    def test_violations_parses_output(self, client, tmp_path, monkeypatch):
        """Gatekeeper output is parsed into structured violations."""
        # Reset cache to force fresh run
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", None)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", 0.0)

        # Create fake gatekeeper script
        gatekeeper_dir = tmp_path / "projects" / "ecos" / "scripts"
        gatekeeper_dir.mkdir(parents=True)
        gatekeeper = gatekeeper_dir / "contract_gatekeeper.py"
        gatekeeper.write_text("# stub")
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)

        # Mock parse_text output
        mock_output = """projects/foo/bar.py
42: direct write violation
99: another violation
projects/baz.py
7: spaced violation"""
        mock_proc = MagicMock(returncode=1, stdout=mock_output, stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            resp = client.get("/api/omos/violations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["passed"] is False
        assert len(data["violations"]) == 3
        assert data["violations"][0]["file"] == "projects/foo/bar.py"
        assert data["violations"][0]["line"] == 42
        assert data["violations"][0]["detail"] == "direct write violation"


class TestOmosFixDrift:
    """Cover api_omos.py:581-603 (fix-drift endpoint)."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_fix_drift_success(self, client):
        mock_proc = MagicMock(returncode=0, stdout="Fixed 3 issues", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            resp = client.post("/api/omos/fix-drift", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["returncode"] == 0
        assert "Fixed 3 issues" in data["stdout"]

    def test_fix_drift_failure(self, client):
        mock_proc = MagicMock(returncode=1, stdout="partial", stderr="warning")
        with patch("subprocess.run", return_value=mock_proc):
            resp = client.post("/api/omos/fix-drift", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["returncode"] == 1
        assert "warning" in data["stderr"]


class TestOmosCircuitBreak:
    """Cover api_omos.py:674-699 (circuit-break endpoint)."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_circuit_break(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value=True, create=True) as mock_set:
            resp = client.post("/api/omos/circuit-break", json={"broken": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["circuit_broken"] is True
        mock_set.assert_called_once()


class TestOmosBudget:
    """Cover api_omos.py:701-726 (budget endpoint)."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_budget(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value=True, create=True) as mock_set:
            resp = client.post("/api/omos/budget", json={"budget": 100.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        mock_set.assert_called_once()
