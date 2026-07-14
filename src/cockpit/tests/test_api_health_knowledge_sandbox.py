"""Tests for cockpit API health, knowledge, sandbox — coverage improvement."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_health, api_knowledge, api_sandbox


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(api_health.router)
    app.include_router(api_knowledge.router)
    app.include_router(api_sandbox.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestHealthSummary:
    """Cover api_health.py:79-131 (get_health_summary endpoint)."""

    def test_health_summary_complete(self, client):
        l4_data = {"healthy_count": 8, "total_domains": 10, "domains": [{"signal_count": 5}]}
        services_data = {"today_requests": 42}

        with (
            patch.object(api_health, "run_l4_script", side_effect=[l4_data, services_data]),
            patch.object(
                api_health,
                "read_runtime_services",
                return_value=[
                    {"port_listening": True, "status": "running"},
                    {"status": "active", "health": "healthy"},
                ],
            ),
        ):
            resp = client.get("/api/health/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["health_score"] == 80  # 8/10 * 100
        assert data["active_services"] == 2
        assert data["total_services"] == 2
        assert data["today_requests"] == 42
        assert data["data_quality"] == "complete"
        assert len(data["degraded_reasons"]) == 0

    def test_health_summary_degraded(self, client):
        with (
            patch.object(api_health, "run_l4_script", side_effect=[None, None]),
            patch.object(api_health, "read_runtime_services", return_value=[]),
        ):
            resp = client.get("/api/health/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["data_quality"] == "unavailable"
        assert len(data["degraded_reasons"]) == 3

    def test_health_summary_partial(self, client):
        l4_data = {"healthy_count": 5, "total_domains": 10, "domains": []}

        with (
            patch.object(api_health, "run_l4_script", side_effect=[l4_data, None]),
            patch.object(api_health, "read_runtime_services", return_value=[]),
        ):
            resp = client.get("/api/health/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["data_quality"] == "partial"

    def test_is_active_service(self):
        """Cover api_health.py:69-76."""
        assert api_health.is_active_service({"port_listening": True}) is True
        assert api_health.is_active_service({"status": "running", "health": "healthy"}) is True
        assert api_health.is_active_service({"status": "active"}) is True
        assert api_health.is_active_service({"status": "stopped"}) is False
        assert api_health.is_active_service({"status": "running", "health": "unhealthy"}) is False

    def test_read_runtime_services_empty(self):
        """Cover api_health.py:52-66."""
        with patch("cockpit.adapters.runtime.i0_services", None, create=True):
            result = api_health.read_runtime_services()
        assert result == []

    def test_read_runtime_services_with_data(self):
        mock_i0 = MagicMock(
            return_value=[
                {"name": "svc1", "status": "running"},
                {"name": "svc2", "status": "stopped"},
            ]
        )
        with patch("cockpit.adapters.runtime.i0_services", mock_i0, create=True):
            result = api_health.read_runtime_services()
        assert len(result) == 2


class TestKnowledgeAPI:
    """Cover api_knowledge.py endpoints."""

    def test_search(self, client):
        with patch("cockpit.adapters.agora.resolve_bos_uri", return_value={"status": "ok", "results": []}):
            resp = client.post("/api/knowledge/search", json={"query": "test", "limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_search_missing_query(self, client):
        resp = client.post("/api/knowledge/search", json={})
        assert resp.status_code == 400

    def test_put(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        resp = client.post(
            "/api/knowledge/put",
            json={
                "slug": "test-card",
                "title": "Test",
                "content": "Test content",
                "tags": ["test"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_put_missing_fields(self, client):
        resp = client.post("/api/knowledge/put", json={"slug": "test"})
        assert resp.status_code == 400


class TestSandboxAPI:
    """Cover api_sandbox.py endpoints."""

    def test_execute(self, client):
        mock_result = MagicMock(success=True, duration_ms=10.0, stdout="hello", output="hello", error=None)
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = mock_result

        import sys
        import types

        mock_module = types.ModuleType("runtime.executor.sandbox")
        mock_module.Sandbox = mock_sandbox
        sys.modules["runtime.executor.sandbox"] = mock_module

        try:
            resp = client.post("/api/sandbox/execute", json={"code": "print('hello')"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["stdout"] == "hello"
        finally:
            del sys.modules["runtime.executor.sandbox"]

    def test_execute_missing_code(self, client):
        # Without runtime.executor.sandbox module, report a clear capability gap.
        resp = client.post("/api/sandbox/execute", json={})
        assert resp.status_code == 503
        assert resp.json()["status"] == "unavailable"
