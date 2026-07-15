from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web import api_alerts


def test_alert_rules_route_is_not_captured_by_alert_id_route():
    response = TestClient(app).get("/api/alerts/rules")

    assert response.status_code == 200
    assert any(item["id"] == "rule-1" for item in response.json()["items"])


def test_custom_alert_rule_round_trips_and_can_be_toggled():
    client = TestClient(app)
    api_alerts.rules_store.clear()

    created = client.post(
        "/api/alerts/rules",
        json={"name": "测试规则", "condition": "latency > 1s", "channels": ["email"]},
    )
    assert created.status_code == 200
    rule_id = created.json()["id"]

    updated = client.patch(f"/api/alerts/rules/{rule_id}", json={"enabled": False})
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    listed = client.get("/api/alerts/rules")
    custom = next(item for item in listed.json()["items"] if item["id"] == rule_id)
    assert custom["enabled"] is False

    api_alerts.rules_store.clear()


def test_builtin_alert_rule_toggle_is_read_back_as_an_override():
    api_alerts.rule_override_store.clear()
    client = TestClient(app)

    updated = client.patch("/api/alerts/rules/rule-1", json={"enabled": False})
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    listed = client.get("/api/alerts/rules")
    builtin = next(item for item in listed.json()["items"] if item["id"] == "rule-1")
    assert builtin["enabled"] is False
    api_alerts.rule_override_store.clear()


def test_alert_action_state_survives_refresh(monkeypatch):
    api_alerts.alert_state_store.clear()
    monkeypatch.setattr(
        api_alerts,
        "generate_alerts_from_l4_data",
        lambda: [
            {
                "id": "alert-test",
                "level": "warning",
                "source": "test",
                "message": "test alert",
                "status": "active",
                "created_at": "now",
                "updated_at": "now",
            }
        ],
    )
    client = TestClient(app)

    response = client.post("/api/alerts/alert-test/acknowledge", json={})
    assert response.status_code == 200
    refreshed = client.get("/api/alerts")

    assert refreshed.status_code == 200
    assert refreshed.json()["items"][0]["status"] == "acknowledged"
    api_alerts.alert_state_store.clear()
