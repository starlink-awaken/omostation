"""Tests for cockpit API omos — full endpoint coverage."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOmosStatusHealth:
    """Cover api_omos.py:56-108."""

    def test_get_status_with_files(self, client, tmp_path, monkeypatch):
        omo_dir = tmp_path / ".omo" / "state"
        omo_dir.mkdir(parents=True)
        (omo_dir / "system.yaml").write_text("current_phase: P42\nhealth_score: 95\n")
        (omo_dir / "health.yaml").write_text("health_score: 90\n")
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        resp = client.get("/api/omos/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "converged"

    def test_get_status_no_files(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        resp = client.get("/api/omos/status")
        assert resp.status_code == 200

    def test_get_health(self, client):
        resp = client.get("/api/omos/health")
        assert resp.status_code == 200


class TestOmosThoughts:
    """Cover api_omos.py:693-720."""

    def test_get_thoughts(self, client):
        resp = client.get("/api/omos/thoughts")
        assert resp.status_code == 200


class TestOmosViolations:
    """Cover api_omos.py:578-645."""

    def test_get_violations_no_gatekeeper(self, client, tmp_path, monkeypatch):
        """When gatekeeper script doesn't exist, returns error."""
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", None, raising=False)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", 0.0, raising=False)
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        resp = client.get("/api/omos/violations")
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_get_violations_cached(self, client, monkeypatch):
        cached = {"status": "ok", "passed": True, "violations": []}
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", cached, raising=False)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", __import__("time").time(), raising=False)
        resp = client.get("/api/omos/violations")
        assert resp.status_code == 200
        assert resp.json() == cached


class TestOmosGovernance:
    """Cover api_omos.py:645-690."""

    def test_circuit_break(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value=True):
            resp = client.post("/api/omos/circuit-break", json={"broken": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_circuit_break_failure(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value=False):
            resp = client.post("/api/omos/circuit-break", json={"broken": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_budget(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value=True):
            resp = client.post("/api/omos/budget", json={"budget": 50.0})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_budget_failure(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value=False):
            resp = client.post("/api/omos/budget", json={"budget": 100.0})
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
