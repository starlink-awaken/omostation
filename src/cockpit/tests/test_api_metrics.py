"""Metrics trend truthfulness tests."""

from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


def test_metrics_trend_does_not_fabricate_history_when_l4_is_unavailable(monkeypatch):
    monkeypatch.setattr("cockpit.web.api_metrics.run_l4_script", lambda *_args, **_kwargs: None)

    response = TestClient(app).get("/api/metrics/trend", params={"range": "24h"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["health_score"] == []
    assert payload["requests"] == []
    assert payload["error_rate"] == []
    assert payload["data_quality"] == "unavailable"
