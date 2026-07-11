from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


def test_l4_health_exposes_unavailable_reason(monkeypatch):
    monkeypatch.setattr("cockpit.web.api_l4.run_l4_script", lambda *_args, **_kwargs: None)

    payload = TestClient(app).get("/api/l4/health").json()

    assert payload["data_quality"] == "unavailable"
    assert payload["degraded_reasons"]
    assert payload["configuration"]["path"].endswith("l4_domain_paths.toml")


def test_l4_health_marks_script_data_live(monkeypatch):
    monkeypatch.setattr(
        "cockpit.web.api_l4.run_l4_script",
        lambda *_args, **_kwargs: {"health_rate": "100.0%"},
    )

    payload = TestClient(app).get("/api/l4/health").json()

    assert payload["data_quality"] == "live"
    assert payload["source"] == "l4-kernel-script"
