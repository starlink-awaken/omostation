"""BOS metrics must expose evidence quality instead of synthetic values."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_bos_metrics_is_unavailable_without_evidence(monkeypatch, tmp_path: Path):
    from cockpit.web import api_bos

    monkeypatch.setattr(api_bos, "WORKSPACE_ROOT", tmp_path)
    app = FastAPI()
    app.include_router(api_bos.router)

    response = TestClient(app).get("/api/bos/metrics")

    assert response.status_code == 503
    assert response.json()["data_quality"] == "unavailable"
    assert response.json()["summary"]["total_calls"] == 0


def test_bos_metrics_route_is_unique_in_dashboard_app():
    from cockpit.dashboard_server import app

    routes = [route for route in app.routes if getattr(route, "path", None) == "/api/bos/metrics"]

    assert len(routes) == 1


def test_compute_wakeup_route_returns_command_result(monkeypatch, tmp_path: Path):
    from cockpit.web import api_compute

    class Result:
        returncode = 0
        stdout = "wake sent"
        stderr = ""

    monkeypatch.setattr(api_compute, "get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(api_compute.subprocess, "run", lambda *args, **kwargs: Result())
    app = FastAPI()
    app.include_router(api_compute.router)

    response = TestClient(app).post("/api/governance/compute/wakeup", json={"node_id": "node-offline"})

    assert response.status_code == 200
    assert response.json()["success"] is True
