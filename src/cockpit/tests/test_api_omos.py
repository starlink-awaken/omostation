"""Tests for cockpit API omos — status/health endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOmosStatusHealth:
    """Cover api_omos.py:56-108."""

    def test_get_status_with_files(self, client, tmp_path, monkeypatch):
        """Status endpoint reads system.yaml and health.yaml."""
        omo_dir = tmp_path / ".omo" / "state"
        omo_dir.mkdir(parents=True)
        (omo_dir / "system.yaml").write_text("current_phase: P42\nhealth_score: 95\ncompleted_tasks: 100\n")
        (omo_dir / "health.yaml").write_text(
            "health_score: 90\nanomaly_count: 2\ntotal_tasks: 50\ndone: 40\nplanned: 5\n"
        )

        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)

        resp = client.get("/api/omos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "converged"
        assert data["system"]["health_score"] == 95
        assert data["governance"]["health_score"] == 90

    def test_get_status_no_files(self, client, tmp_path, monkeypatch):
        """Status endpoint handles missing files gracefully."""
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)

        resp = client.get("/api/omos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "converged"
        assert data["system"]["current_phase"] is None

    def test_get_status_exception_returns_degraded(self, client, monkeypatch):
        """Status endpoint returns degraded on error."""
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", None)

        resp = client.get("/api/omos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"

    def test_get_health(self, client):
        """Health endpoint returns ok."""
        resp = client.get("/api/omos/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "omo-dashboard-converged"
