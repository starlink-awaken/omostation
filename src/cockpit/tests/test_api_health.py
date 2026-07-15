"""Health summary truthfulness tests."""

from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web import api_health


def test_health_summary_uses_runtime_probe_when_l4_data_is_unavailable(monkeypatch):
    monkeypatch.setattr("cockpit.web.api_health.run_l4_script", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "cockpit.web.api_health.read_runtime_services",
        lambda: [
            {"name": "gateway", "status": "running", "port_listening": True, "health": "healthy"},
            {"name": "worker", "status": "stopped", "port_listening": False, "health": "unknown"},
        ],
    )

    response = TestClient(app).get("/api/health/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_services"] == 1
    assert payload["total_services"] == 2
    assert payload["health_score"] == 50
    assert payload["data_quality"] == "partial"
    assert "L4 health_monitor.py unavailable" in payload["degraded_reasons"]


def test_health_summary_reads_active_tasks_from_omo_queue(monkeypatch, tmp_path):
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    active_dir.mkdir(parents=True)
    (active_dir / "one.yaml").write_text("id: one\n", encoding="utf-8")
    (active_dir / "two.yaml").write_text("id: two\n", encoding="utf-8")
    monkeypatch.setattr("cockpit.web.api_health.WORKSPACE_DIR", tmp_path)

    assert api_health.read_active_task_count() == 2
