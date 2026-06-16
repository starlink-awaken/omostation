"""Extended tests for web/app.py — POST endpoints, auth, rate limiting, proxy."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import web.app as _webapp
from web.app import app


@pytest.fixture
def auth_client():
    """TestClient with API key enabled, rate limit disabled."""
    with patch.object(_webapp, "API_KEY", "test-key-123"), \
         patch.object(_webapp, "_RATE_LIMIT_MAX", 0):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, "test-key-123"


@pytest.fixture
def client():
    with patch.object(_webapp, "_RATE_LIMIT_MAX", 0):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ── Auth middleware ──────────────────────────────────────────────────────────


class TestAuthMiddleware:
    def test_read_endpoints_no_auth_needed(self, client):
        r = client.get("/api/services")
        assert r.status_code == 200

    def test_write_endpoint_without_key_rejected(self, client):
        r = client.post("/api/discover")
        assert r.status_code == 401

    def test_write_endpoint_wrong_key_rejected(self, auth_client):
        c, _ = auth_client
        r = c.post("/api/discover", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401

    def test_write_endpoint_correct_key_accepted(self, auth_client):
        c, key = auth_client
        r = c.post("/api/discover", headers={"X-API-Key": key})
        assert r.status_code == 200


# ── POST /api/discover ──────────────────────────────────────────────────────


class TestDiscoverAPI:
    def test_discover(self, auth_client):
        c, key = auth_client
        r = c.post("/api/discover", headers={"X-API-Key": key})
        assert r.status_code == 200
        data = r.json()
        assert "discovered" in data
        assert "total" in data


# ── POST /api/register ──────────────────────────────────────────────────────


class TestRegisterAPI:
    def test_register(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/register",
            headers={"X-API-Key": key},
            data={"name": "test-svc", "protocol": "mcp", "tags": "test,l2"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "registered"
        assert data["name"] == "test-svc"

    def test_register_invalid_json_config(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/register",
            headers={"X-API-Key": key},
            data={"name": "test", "protocol_config": "not-json"},
        )
        assert r.status_code == 400


# ── POST /api/clear ─────────────────────────────────────────────────────────


class TestClearAPI:
    def test_clear(self, auth_client):
        c, key = auth_client
        r = c.post("/api/clear", headers={"X-API-Key": key})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "cleared"


# ── POST /api/event-publish ──────────────────────────────────────────────────


class TestEventPublishAPI:
    def test_event_publish(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/event-publish",
            headers={"X-API-Key": key},
            data={"event_type": "test:event", "payload": '{"msg": "hello"}', "source": "test"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "event_id" in data
        assert data["status"] == "published"

    def test_event_publish_invalid_json(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/event-publish",
            headers={"X-API-Key": key},
            data={"event_type": "test", "payload": "not-json", "source": "test"},
        )
        assert r.status_code == 200


# ── POST /api/pipeline ──────────────────────────────────────────────────────


class TestPipelineRunAPI:
    def test_pipeline_run(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/pipeline",
            headers={"X-API-Key": key},
            data={"name": "test-pipeline", "goal": "test", "mode": "sequential"},
        )
        assert r.status_code == 200

    def test_pipeline_run_parallel(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/pipeline",
            headers={"X-API-Key": key},
            data={"name": "test-pipeline", "mode": "parallel"},
        )
        assert r.status_code == 200


# ── POST /api/instance ──────────────────────────────────────────────────────


class TestInstanceAPI:
    def test_add_instance(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/instance",
            headers={"X-API-Key": key},
            json={"service": "test-svc", "mcp_endpoint": "http://localhost:9999"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_add_instance_missing_fields(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/instance",
            headers={"X-API-Key": key},
            json={"service": "", "mcp_endpoint": ""},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "error"


# ── POST /api/sandbox/execute ───────────────────────────────────────────────


class TestSandboxAPI:
    def test_sandbox_empty_code(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/sandbox/execute",
            headers={"X-API-Key": key},
            json={"code": ""},
        )
        assert r.status_code == 400

    def test_sandbox_error(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/sandbox/execute",
            headers={"X-API-Key": key},
            json={"code": "import nonexistent_module_xyz"},
        )
        assert r.status_code in (200, 500)


# ── POST /api/knowledge ─────────────────────────────────────────────────────


class TestKnowledgeAPI:
    def test_knowledge_put_missing_fields(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/knowledge/put",
            headers={"X-API-Key": key},
            json={"slug": "", "title": "", "content": ""},
        )
        assert r.status_code == 400

    def test_knowledge_search_missing_query(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/knowledge/search",
            headers={"X-API-Key": key},
            json={"query": ""},
        )
        assert r.status_code == 400


# ── POST /api/webhook/events ────────────────────────────────────────────────


class TestWebhookAPI:
    def test_webhook_receive(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/webhook/events",
            headers={"X-API-Key": key},
            json={"event_type": "webhook:test", "payload": {}, "source": "external"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "received"

    def test_webhook_missing_event_type(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/webhook/events",
            headers={"X-API-Key": key},
            json={"event_type": "", "payload": {}},
        )
        assert r.status_code == 400


# ── POST /api/a2a/push-notification ─────────────────────────────────────────


class TestA2APushNotification:
    def test_register_push(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/a2a/push-notification",
            headers={"X-API-Key": key},
            json={"callback_url": "http://example.com/events", "event_types": ["registry:*"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "subscriptions" in data

    def test_register_push_missing_url(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/a2a/push-notification",
            headers={"X-API-Key": key},
            json={"callback_url": ""},
        )
        assert r.status_code == 400


# ── POST /api/research endpoints ────────────────────────────────────────────


class TestResearchWriteAPI:
    def test_archive_stub_returns_ok(self, auth_client):
        c, key = auth_client
        r = c.post("/api/research/99999/archive", headers={"X-API-Key": key})
        assert r.status_code == 200

    def test_publish_empty_path(self, auth_client):
        c, key = auth_client
        r = c.post("/api/research/99999/publish", headers={"X-API-Key": key})
        assert r.status_code in (200, 400)

    def test_sync_empty_path(self, auth_client):
        c, key = auth_client
        r = c.post("/api/research/99999/sync", headers={"X-API-Key": key})
        assert r.status_code in (200, 400)

    def test_unarchive_stub_returns_ok(self, auth_client):
        c, key = auth_client
        r = c.post("/api/research/99999/unarchive", headers={"X-API-Key": key})
        assert r.status_code == 200

    def test_tag_empty(self, auth_client):
        c, key = auth_client
        r = c.post("/api/research/1/tag", headers={"X-API-Key": key})
        assert r.status_code == 400

    def test_rename_empty(self, auth_client):
        c, key = auth_client
        r = c.post("/api/research/1/rename", headers={"X-API-Key": key})
        assert r.status_code == 400

    def test_ask_empty(self, auth_client):
        c, key = auth_client
        r = c.post("/api/research/1/ask", headers={"X-API-Key": key})
        assert r.status_code == 400


# ── POST /api/a2a/tasks ────────────────────────────────────────────────────


class TestA2ATasksAPI:
    def test_send_missing_tool(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/a2a/tasks/send",
            headers={"X-API-Key": key},
            json={"tool_name": ""},
        )
        assert r.status_code == 400

    def test_get_task_not_found_or_unavailable(self, client):
        r = client.get("/api/a2a/tasks/nonexistent")
        assert r.status_code in (404, 500)

    def test_cancel_task_not_found_or_unavailable(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/a2a/tasks/nonexistent/cancel",
            headers={"X-API-Key": key},
        )
        assert r.status_code in (400, 500)

    def test_list_tasks_or_unavailable(self, client):
        r = client.get("/api/a2a/tasks")
        assert r.status_code in (200, 500)


# ── Rate limiting ────────────────────────────────────────────────────────────


class TestRateLimiting:
    def test_rate_limit_triggers(self):
        with patch.object(_webapp, "_RATE_LIMIT_MAX", 3):
            with TestClient(app, raise_server_exceptions=False) as c:
                for _ in range(3):
                    c.get("/api/services")
                r = c.get("/api/services")
                assert r.status_code == 429


# ── WebSocket ────────────────────────────────────────────────────────────────


class TestWebSocket:
    def test_ws_connects(self, client):
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert "services" in data
            assert "healthy" in data
            assert "total" in data


# ── Pipeline DAG with registered name ────────────────────────────────────────


class TestPipelineDAG:
    def test_pipeline_dag_empty_for_stub(self, client):
        r = client.get("/api/pipeline/test-pipeline/dag")
        data = r.json()
        assert data["status"] == "error"
        assert "not found" in data["error"].lower()


# ── POST /api/instance with SSRF URL ────────────────────────────────────────


class TestInstanceSSRF:
    def test_instance_with_internal_url(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/instance",
            headers={"X-API-Key": key},
            json={"service": "test", "mcp_endpoint": "http://localhost:8080"},
        )
        assert r.status_code == 200


# ── POST /api/knowledge with valid data but missing proxy ────────────────────


class TestKnowledgeProxyError:
    def test_knowledge_put_proxy_error(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/knowledge/put",
            headers={"X-API-Key": key},
            json={"slug": "test", "title": "Test", "content": "Hello"},
        )
        assert r.status_code in (200, 500)

    def test_knowledge_search_proxy_error(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/knowledge/search",
            headers={"X-API-Key": key},
            json={"query": "test"},
        )
        assert r.status_code in (200, 500)


# ── Research POST with actual data ──────────────────────────────────────────


class TestResearchWriteWithData:
    def test_tag_with_data(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/research/1/tag?tags=ai,ml",
            headers={"X-API-Key": key},
        )
        assert r.status_code == 200

    def test_rename_with_data(self, auth_client):
        c, key = auth_client
        r = c.post(
            "/api/research/1/rename?title=New%20Title",
            headers={"X-API-Key": key},
        )
        assert r.status_code == 200


# ── Governance routes ────────────────────────────────────────────────────────


class TestGovernanceRoutes:
    def test_omo_status(self, client):
        r = client.get("/api/omo/status")
        assert r.status_code == 200
        data = r.json()
        assert "phase" in data
        assert "health_score" in data

    def test_omo_debt(self, client):
        r = client.get("/api/omo/debt")
        assert r.status_code == 200

    def test_omo_report(self, client):
        r = client.get("/api/omo/report")
        assert r.status_code == 200
        data = r.json()
        assert "phase" in data

    def test_ecos_status(self, client):
        r = client.get("/api/ecos/status")
        assert r.status_code == 200
        data = r.json()
        assert "m0_snapshot" in data

    def test_e2e(self, client):
        r = client.get("/api/e2e")
        assert r.status_code == 200


# ── Runtime/MetaOS/L4 routes ────────────────────────────────────────────────


class TestLayerStatusRoutes:
    def test_runtime_status(self, client):
        r = client.get("/api/runtime/status")
        assert r.status_code == 200

    def test_metaos_status(self, client):
        r = client.get("/api/metaos/status")
        assert r.status_code == 200

    def test_l4kernel_status(self, client):
        r = client.get("/api/l4kernel/status")
        assert r.status_code == 200


# ── API v1 routes ────────────────────────────────────────────────────────────


class TestAPIv1:
    def test_v1_status(self, client):
        r = client.get("/api/v1/status")
        assert r.status_code == 200
        data = r.json()
        assert data["version"] == "v1"
        assert "services" in data

    def test_v1_governance(self, client):
        r = client.get("/api/v1/governance")
        assert r.status_code == 200
        data = r.json()
        assert data["version"] == "v1"
        assert "omo" in data
        assert "ecos" in data


# ── Dev routes ────────────────────────────────────────────────────────────────


class TestDevRoutes:
    def test_kos_search_empty(self, client):
        r = client.get("/dev/kos/api/search")
        assert r.status_code == 200
        assert r.json()["results"] == []

    def test_kos_search_with_query(self, client):
        r = client.get("/dev/kos/api/search?q=test")
        assert r.status_code == 200

    def test_minerva_status(self, client):
        r = client.get("/dev/minerva/api/status")
        assert r.status_code == 200

    def test_ontoderive_status(self, client):
        r = client.get("/dev/ontoderive/api/status")
        assert r.status_code == 200

    def test_forge_status(self, client):
        r = client.get("/dev/forge/api/status")
        assert r.status_code == 200


# ── eCOS detailed routes ────────────────────────────────────────────────────


class TestEcosDetailedRoutes:
    def test_ecos_ssb(self, client):
        r = client.get("/api/ecos/ssb")
        assert r.status_code == 200

    def test_ecos_watchdog(self, client):
        r = client.get("/api/ecos/watchdog")
        assert r.status_code == 200


# ── OMO healing routes ──────────────────────────────────────────────────────


class TestOmoHealingRoutes:
    def test_healing_status(self, client):
        r = client.get("/api/omo/healing/status")
        assert r.status_code == 200

    def test_healing_fixes(self, client):
        r = client.get("/api/omo/healing/fixes")
        assert r.status_code == 200
        data = r.json()
        assert "fixes" in data

    def test_healing_trends(self, client):
        r = client.get("/api/omo/healing/trends")
        assert r.status_code == 200


# ── Auth management routes ───────────────────────────────────────────────────


class TestAuthRoutes:
    def test_auth_status(self, client):
        r = client.get("/api/auth/status")
        assert r.status_code == 200
        data = r.json()
        assert "api_key_configured" in data

    def test_login(self, client):
        r = client.post(
            "/api/auth/login",
            json={"username": "test-user"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert "expires_at" in data

    def test_login_no_username(self, client):
        r = client.post(
            "/api/auth/login",
            json={},
        )
        assert r.status_code == 400

    def test_logout(self, client):
        # First login
        r = client.post("/api/auth/login", json={"username": "test"})
        token = r.json()["token"]

        # Then logout
        r = client.post("/api/auth/logout", json={"token": token})
        assert r.status_code == 200

    def test_logout_invalid_token(self, client):
        r = client.post("/api/auth/logout", json={"token": "invalid"})
        assert r.status_code == 200
        assert r.json()["status"] == "not_found"


# ── BOS URI Gateway routes ───────────────────────────────────────────────────


class TestBosRoutes:
    def test_bos_status(self, client):
        r = client.get("/api/bos/status")
        assert r.status_code == 200
        data = r.json()
        assert "domains" in data
        assert len(data["domains"]) == 5

    def test_bos_domains(self, client):
        r = client.get("/api/bos/domains")
        assert r.status_code == 200
        data = r.json()
        assert "domains" in data
        assert len(data["domains"]) == 5

    def test_bos_discover(self, client):
        r = client.get("/api/bos/discover")
        assert r.status_code == 200
        data = r.json()
        assert "services" in data
        assert len(data["services"]) >= 5


# ── Auto Discovery routes ────────────────────────────────────────────────────


class TestAutoDiscovery:
    def test_auto_discover(self, client):
        r = client.post("/api/discover/auto")
        assert r.status_code == 200
        data = r.json()
        assert "discovered" in data
        assert "services" in data
