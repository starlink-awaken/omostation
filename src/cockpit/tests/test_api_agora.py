"""Agora/control-plane API regression tests."""

from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


def test_system_metrics_route_returns_series_for_supported_range():
    response = TestClient(app).get("/api/metrics/system", params={"range": "1h"})

    assert response.status_code == 200
    payload = response.json()
    assert {"cpu", "memory", "disk", "network"}.issubset(payload)
    assert payload["source"] == "psutil"
    assert payload["data_quality"] == "live"
    assert all(isinstance(payload[key], list) for key in ("cpu", "memory", "disk", "network"))


def test_system_metrics_route_supports_longer_range():
    response = TestClient(app).get("/api/metrics/system", params={"range": "24h"})

    assert response.status_code == 200
    assert response.json()["sample_count"] >= 1


def test_services_status_uses_runtime_probe_without_synthetic_load(monkeypatch):
    monkeypatch.setattr(
        "cockpit.web.api_agora._read_runtime_services",
        lambda: [{"name": "gateway", "status": "running", "port_listening": True, "health": "healthy"}],
    )

    response = TestClient(app).get("/api/services/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "runtime-probe"
    assert payload["items"][0]["name"] == "gateway"
    assert payload["items"][0]["cpu"] is None
    assert payload["items"][0]["memory"] is None


def test_register_instance_rejects_invalid_service_contract():
    response = TestClient(app).post(
        "/api/instance",
        data={"service": "bad service", "mcp_endpoint": "not-a-uri"},
    )

    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_register_instance_accepts_http_mcp_endpoint(monkeypatch):
    registered = []
    task_calls = []

    class FakeService:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRegistry:
        def unregister(self, _service):
            return None

        def register(self, service):
            registered.append(service.kwargs)

    monkeypatch.setattr("cockpit.adapters.agora.Service", FakeService)
    monkeypatch.setattr("cockpit.adapters.agora.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr(
        "omo.omo_ingress_task_lifecycle.create_planned_task",
        lambda *args, **kwargs: task_calls.append(kwargs) or kwargs["task_data"],
    )
    response = TestClient(app).post(
        "/api/instance",
        data={"service": "mesh-router", "mcp_endpoint": "http://127.0.0.1:7437/sse"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["task_id"] == "cockpit-mcp-registration-mesh-router"
    assert response.json()["task_created"] is True
    assert registered == [{"name": "mesh-router", "protocol": "mcp", "mcp_endpoint": "http://127.0.0.1:7437/sse"}]
    assert task_calls[0]["source_ref"] == "cockpit:mcp-registration:mesh-router"
    assert task_calls[0]["task_data"]["risk_level"] == "L1"
