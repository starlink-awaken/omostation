"""Tests for web/app.py — Agora Dashboard FastAPI server."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web.app import app


@pytest.fixture
def client():
    """TestClient with lifespan triggered (seeds registry + emits startup event)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── GET endpoints (read-only, no auth) ──────────────────────────────────────


class TestDashboardPage:
    def test_root_returns_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "")


class TestHealthEndpoints:
    def test_healthz(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["service"] == "agora"

    def test_api_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert isinstance(data["services"], int)
        assert isinstance(data["healthy"], int)


class TestServicesAPI:
    def test_list_services(self, client):
        r = client.get("/api/services")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 12
        svc = data[0]
        assert "name" in svc
        assert "protocol" in svc
        assert "healthy" in svc
        assert "tags" in svc

    def test_service_fields_complete(self, client):
        r = client.get("/api/services")
        data = r.json()
        svc = data[0]
        expected_fields = {
            "name", "description", "protocol", "protocol_config",
            "mcp_endpoint", "health_endpoint", "circuit", "healthy",
            "failure_count", "port", "tags", "instances",
        }
        assert expected_fields.issubset(set(svc.keys()))


class TestComputeAPI:
    def test_compute_returns_data(self, client):
        r = client.get("/api/compute")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "provider" in data
        assert "cost_board" in data
        assert "topology" in data
        assert "recent_traffic" in data

    def test_compute_summary_fields(self, client):
        r = client.get("/api/compute")
        s = r.json()["summary"]
        assert "total_calls" in s
        assert "total_input_tokens" in s
        assert "total_output_tokens" in s
        assert "total_estimated_cost_usd" in s

    def test_compute_cost_board_fields(self, client):
        r = client.get("/api/compute")
        cb = r.json()["cost_board"]
        assert "selected_cloud_model" in cb
        assert "intercepted_calls" in cb
        assert "saved_vs_cloud_usd" in cb
        assert "actual_cloud_cost_usd" in cb
        assert "actual_local_cost_usd" in cb

    def test_compute_topology(self, client):
        r = client.get("/api/compute")
        topo = r.json()["topology"]
        assert isinstance(topo, list)
        assert len(topo) >= 4
        node_ids = {n["id"] for n in topo}
        assert "local-mac" in node_ids
        assert "cloud-cc-switch" in node_ids


class TestEventLogAPI:
    def test_event_log(self, client):
        r = client.get("/api/event-log")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_event_log_limit(self, client):
        r = client.get("/api/event-log?limit=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) <= 1

    def test_event_has_fields(self, client):
        r = client.get("/api/event-log")
        data = r.json()
        evt = data[0]
        assert "type" in evt
        assert "timestamp" in evt


class TestResearchAPI:
    def test_research_list(self, client):
        r = client.get("/api/research")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_research_with_status(self, client):
        r = client.get("/api/research?status=active")
        assert r.status_code == 200

    def test_research_with_query(self, client):
        r = client.get("/api/research?q=test")
        assert r.status_code == 200

    def test_research_invalid_status(self, client):
        r = client.get("/api/research?status=invalid")
        assert r.status_code == 400

    def test_research_zero_limit(self, client):
        r = client.get("/api/research?limit=0")
        assert r.status_code == 400

    def test_research_detail_not_found(self, client):
        r = client.get("/api/research/99999")
        assert r.status_code == 404


class TestHealthMetrics:
    def test_metrics_history(self, client):
        r = client.get("/api/metrics/history")
        assert r.status_code == 200
        data = r.json()
        assert "latency" in data
        assert "services" in data

    def test_prometheus_metrics(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")


class TestTransitionsAPI:
    def test_transitions(self, client):
        r = client.get("/api/transitions")
        assert r.status_code == 200
        data = r.json()
        assert "transitions" in data
        assert "count" in data
        assert data["count"] >= 12

    def test_service_transitions(self, client):
        r = client.get("/api/transitions/agora")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "agora"


class TestPipelinesAPI:
    def test_pipelines_list(self, client):
        r = client.get("/api/pipelines")
        assert r.status_code == 200
        data = r.json()
        assert "pipelines" in data

    def test_pipeline_dag_not_found(self, client):
        r = client.get("/api/pipeline/nonexistent/dag")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "error"


class TestAgentCardAPI:
    def test_agent_card(self, client):
        r = client.get("/.well-known/agent-card.json")
        assert r.status_code == 200
        data = r.json()
        assert data["format_version"] == "a2a-v1"
        assert "agents" in data
        assert data["count"] >= 12


# ── POST endpoints (write, need auth) ───────────────────────────────────────


class TestWriteEndpointsAuth:
    def test_discover_unauthorized(self, client):
        r = client.post("/api/discover")
        assert r.status_code == 401

    def test_register_unauthorized(self, client):
        r = client.post("/api/register", data={"name": "test"})
        assert r.status_code == 401

    def test_clear_unauthorized(self, client):
        r = client.post("/api/clear")
        assert r.status_code == 401

    def test_pipeline_unauthorized(self, client):
        r = client.post("/api/pipeline", data={"name": "test"})
        assert r.status_code == 401

    def test_event_publish_unauthorized(self, client):
        r = client.post(
            "/api/event-publish",
            data={"event_type": "test", "payload": "{}", "source": "test"},
        )
        assert r.status_code == 401

    def test_sandbox_execute_unauthorized(self, client):
        r = client.post("/api/sandbox/execute", json={"code": "print(1)"})
        assert r.status_code == 401


# ── Rate limiting ────────────────────────────────────────────────────────────


class TestRateLimiting:
    def test_rate_limit_disabled_by_default(self, client):
        for _ in range(5):
            r = client.get("/api/services")
            assert r.status_code == 200


# ── Error responses ──────────────────────────────────────────────────────────


class TestErrorResponses:
    def test_unknown_endpoint(self, client):
        r = client.get("/api/nonexistent")
        assert r.status_code == 404
