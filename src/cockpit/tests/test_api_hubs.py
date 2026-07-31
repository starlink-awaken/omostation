from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.storage import set_data_access
from cockpit.web.api_hubs import build_protocol_hub, build_research_detail, build_research_hub


class ResearchAccess:
    def get_research(self, research_id):
        return {
            "id": research_id,
            "topic": "Cockpit 全站使用路径",
            "summary": "梳理入口和执行闭环",
            "full_text": "完整研究正文",
            "created_at": 1710000000,
            "source_count": 4,
            "tags": ["cockpit"],
            "follow_ups": [{"question": "下一步是什么"}],
            "agent": "researcher",
            "archived_at": None,
            "quarantined_at": None,
        }

    def list_research(self, limit=10, include_quarantined=False, include_archived=False):
        return [
            {
                "id": 7,
                "topic": "Cockpit 全站使用路径",
                "summary": "梳理入口和执行闭环",
                "created_at": 1710000000,
                "source_count": 4,
                "tags": ["cockpit"],
                "follow_ups": [{"question": "下一步是什么"}],
                "agent": "researcher",
                "archived_at": None,
                "quarantined_at": None,
            }
        ]

    def get_research_dossier(self, research_id):
        return {"publications": [{"style": "brief"}]}

    def get_research_timeline(self, research_id):
        return [{"event_type": "published", "description": "已发布", "created_at": 1710000100}]

    def compute_half_life(self, research_id):
        return {"decay": 0.8, "half_life_days": 14, "days_since_active": 2.0}


def test_research_hub_reads_existing_research_storage(monkeypatch):
    set_data_access(ResearchAccess())
    payload = build_research_hub()

    assert payload["status"] == "ok"
    assert payload["summary"]["active"] == 1
    assert payload["summary"]["published"] == 1
    assert payload["summary"]["follow_ups"] == 1
    assert payload["recent"][0]["topic"] == "Cockpit 全站使用路径"
    assert payload["recent"][0]["status"] == "active"
    assert any(command["id"] == "research-publish" for command in payload["commands"])


def test_research_detail_includes_timeline_dossier_and_freshness(monkeypatch):
    set_data_access(ResearchAccess())

    payload = build_research_detail(7)

    assert payload["status"] == "ok"
    assert payload["item"]["topic"] == "Cockpit 全站使用路径"
    assert payload["timeline"][0]["event_type"] == "published"
    assert payload["dossier"]["publications"][0]["style"] == "brief"
    assert payload["half_life"]["decay"] == 0.8


def test_protocol_hub_reads_ecos_registries(monkeypatch):
    import cockpit.adapters.ecos as ecos

    monkeypatch.setattr(ecos, "list_workflows", lambda: [{"name": "daily-check", "steps": 2}])
    monkeypatch.setattr(ecos, "list_actions", lambda: [{"name": "run-check"}])
    monkeypatch.setattr(ecos, "list_backends", lambda: [{"name": "local"}])
    monkeypatch.setattr(ecos, "load_all_workflow_runs", lambda: [{"status": "completed", "name": "daily-check"}])

    payload = build_protocol_hub()

    assert payload["status"] == "ok"
    assert payload["summary"]["workflow_definitions"] == 1
    assert payload["summary"]["workflow_actions"] == 1
    assert payload["summary"]["workflow_backends"] == 1
    assert payload["summary"]["recent_runs"] == 1
    assert payload["recent_workflows"][0]["status"] == "completed"
    assert any(layer["status"] == "ready" for layer in payload["layers"])


def test_hub_routes_are_mounted():
    client = TestClient(app)

    research_response = client.get("/api/cockpit/research-hub")
    protocol_response = client.get("/api/cockpit/protocol-hub")

    assert research_response.status_code == 200
    assert research_response.json()["status"] == "ok"
    assert protocol_response.status_code == 200
    assert protocol_response.json()["status"] == "ok"
