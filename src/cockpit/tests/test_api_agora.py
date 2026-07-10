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
