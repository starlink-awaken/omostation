"""Tests for cockpit API omos — health + thoughts endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOmosHealth:
    """Cover api_omos.py:137-140 (health endpoint)."""

    def test_get_health_returns_ok(self, client):
        resp = client.get("/api/omos/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "omo-dashboard-converged"
        assert data["endpoint"] == "/api/omos/status"


class TestOmosThoughts:
    """Cover api_omos.py:730-822 (virtual board thoughts)."""

    def test_get_thoughts_no_state_files(self, client, tmp_path, monkeypatch):
        """When .omo/state/system.yaml and provider-plane.yaml are missing, returns ok with phase=未知."""
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        resp = client.get("/api/omos/thoughts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "thoughts" in data
        assert len(data["thoughts"]) == 4
        roles = {t["role"] for t in data["thoughts"]}
        assert roles == {"builder", "devil", "sage", "keeper"}

    def test_get_thoughts_healthy_state(self, client, tmp_path, monkeypatch):
        """Healthy state (no violations, no circuit_breaker, health_score>=90) → optimistic narratives."""
        omo_dir = tmp_path / ".omo" / "state"
        omo_dir.mkdir(parents=True)
        (omo_dir / "system.yaml").write_text("current_phase: P42\nhealth_score: 95\n")
        (omo_dir / "provider-plane.yaml").write_text("circuit_broken: false\ndaily_budget: 100.0\n")
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)

        resp = client.get("/api/omos/thoughts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        builder = next(t for t in data["thoughts"] if t["role"] == "builder")
        assert "P42" in builder["content"] or "一切正常" in builder["content"]
