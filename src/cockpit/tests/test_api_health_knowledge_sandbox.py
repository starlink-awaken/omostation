"""Tests for cockpit API health, knowledge, sandbox — coverage improvement."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_health, api_knowledge, api_sandbox


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(api_health.router)
    app.include_router(api_knowledge.router)
    app.include_router(api_sandbox.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestHealthSummary:
    """Cover api_health.py:79-131 (get_health_summary endpoint)."""

    def test_health_summary_complete(self, client):
        l4_data = {"healthy_count": 8, "total_domains": 10, "domains": [{"signal_count": 5}]}
        services_data = {"today_requests": 42}

        with (
            patch.object(api_health, "run_l4_script", side_effect=[l4_data, services_data]),
            patch.object(
                api_health,
                "read_runtime_services",
                return_value=[
                    {"port_listening": True, "status": "running"},
                    {"status": "active", "health": "healthy"},
                ],
            ),
        ):
            resp = client.get("/api/health/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["health_score"] == 80  # 8/10 * 100
        assert data["active_services"] == 2
        assert data["total_services"] == 2
        assert data["today_requests"] == 42
        assert data["data_quality"] == "complete"
        assert len(data["degraded_reasons"]) == 0

    def test_health_summary_degraded(self, client):
        with (
            patch.object(api_health, "run_l4_script", side_effect=[None, None]),
            patch.object(api_health, "read_runtime_services", return_value=[]),
        ):
            resp = client.get("/api/health/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["data_quality"] == "unavailable"
        assert len(data["degraded_reasons"]) == 3

    def test_health_summary_partial(self, client):
        l4_data = {"healthy_count": 5, "total_domains": 10, "domains": []}

        with (
            patch.object(api_health, "run_l4_script", side_effect=[l4_data, None]),
            patch.object(api_health, "read_runtime_services", return_value=[]),
        ):
            resp = client.get("/api/health/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["data_quality"] == "partial"

    def test_is_active_service(self):
        """Cover api_health.py:69-76."""
        assert api_health.is_active_service({"port_listening": True}) is True
        assert api_health.is_active_service({"status": "running", "health": "healthy"}) is True
        assert api_health.is_active_service({"status": "active"}) is True
        assert api_health.is_active_service({"status": "stopped"}) is False
        assert api_health.is_active_service({"status": "running", "health": "unhealthy"}) is False

    def test_read_runtime_services_empty(self):
        """Cover api_health.py:52-66."""
        with patch("cockpit.adapters.runtime.i0_services", None, create=True):
            result = api_health.read_runtime_services()
        assert result == []

    def test_read_runtime_services_with_data(self):
        mock_i0 = MagicMock(
            return_value=[
                {"name": "svc1", "status": "running"},
                {"name": "svc2", "status": "stopped"},
            ]
        )
        with patch("cockpit.adapters.runtime.i0_services", mock_i0, create=True):
            result = api_health.read_runtime_services()
        assert len(result) == 2


class TestKnowledgeAPI:
    """Cover api_knowledge.py endpoints."""

    def test_search(self, client):
        with patch("cockpit.adapters.agora.resolve_bos_uri", return_value={"status": "ok", "results": []}):
            resp = client.post("/api/knowledge/search", json={"query": "test", "limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_search_async_resolver(self, client):
        async def nested_result():
            return {"status": "ok", "results": [{"title": "nested-async"}]}

        with patch(
            "cockpit.adapters.agora.resolve_bos_uri",
            new=AsyncMock(return_value={"status": "ok", "result": nested_result()}),
        ):
            resp = client.post("/api/knowledge/search", json={"query": "test"})
        assert resp.status_code == 200
        assert resp.json()["result"]["result"]["results"][0]["title"] == "nested-async"

    def test_search_missing_query(self, client):
        resp = client.post("/api/knowledge/search", json={})
        assert resp.status_code == 400

    def test_search_rejects_invalid_limit(self, client):
        resp = client.post("/api/knowledge/search", json={"query": "test", "limit": "many"})
        assert resp.status_code == 400

    def test_search_clamps_limit_and_strips_query(self, client):
        with patch("cockpit.adapters.agora.resolve_bos_uri", return_value={"status": "ok", "results": []}) as resolve:
            resp = client.post("/api/knowledge/search", json={"query": "  test  ", "limit": 1000})
        assert resp.status_code == 200
        assert resolve.call_args.args[1] == {"query": "test", "limit": 50}

    def test_put(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        resp = client.post(
            "/api/knowledge/put",
            json={
                "slug": "test-card",
                "title": "Test",
                "content": "Test content",
                "tags": ["test"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["knowledge_ref"] == "memory:test-card"

    def test_put_rejects_path_traversal_slug(self, client):
        resp = client.post(
            "/api/knowledge/put",
            json={"slug": "../escape", "title": "Test", "content": "Content", "tags": []},
        )
        assert resp.status_code == 400

    def test_put_rejects_non_string_tags(self, client):
        resp = client.post(
            "/api/knowledge/put",
            json={"slug": "test-card", "title": "Test", "content": "Content", "tags": [1]},
        )
        assert resp.status_code == 400

    def test_put_missing_fields(self, client):
        resp = client.post("/api/knowledge/put", json={"slug": "test"})
        assert resp.status_code == 400

    def test_search_via_http_network_resolver(self, client):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"status": "ok", "results": [{"title": "network-resolved"}]}
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            resp = client.post("/api/knowledge/search", json={"query": "network-test"})
        assert resp.status_code == 200
        assert resp.json()["result"]["results"][0]["title"] == "network-resolved"

    def test_put_emits_card_updated_event(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        mock_client = AsyncMock()
        mock_post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_client.__aenter__.return_value.post = mock_post
        with patch("httpx.AsyncClient", return_value=mock_client):
            resp = client.post(
                "/api/knowledge/put",
                json={
                    "slug": "event-card",
                    "title": "Event Test",
                    "content": "Event Content",
                    "tags": ["event"],
                },
            )
        assert resp.status_code == 200
        assert mock_post.call_count >= 1


class TestSandboxAPI:
    """Cover api_sandbox.py endpoints."""

    def test_execute(self, client):
        mock_result = MagicMock(success=True, duration_ms=10.0, stdout="hello", output="hello", error=None)
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = mock_result

        import sys
        import types

        mock_module = types.ModuleType("runtime.executor.sandbox")
        mock_module.Sandbox = mock_sandbox
        sys.modules["runtime.executor.sandbox"] = mock_module

        try:
            resp = client.post("/api/sandbox/execute", json={"code": "print('hello')"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["stdout"] == "hello"
        finally:
            del sys.modules["runtime.executor.sandbox"]

    def test_execute_missing_code(self, client):
        # Validate the request before reporting runtime capability availability.
        resp = client.post("/api/sandbox/execute", json={})
        assert resp.status_code == 400
        assert resp.json()["error"] == "code is required"

    def test_execute_rejects_non_object_body(self, client):
        resp = client.post("/api/sandbox/execute", json=["print('hello')"])
        assert resp.status_code == 422

    def test_execute_rejects_oversized_code(self, client):
        resp = client.post("/api/sandbox/execute", json={"code": "x" * 20001})
        assert resp.status_code == 413


class TestKnowledgeIndexer:
    """Tests for knowledge_indexer.py — Consumer side of ADR-0294 event pipeline."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_event_bus(self):
        """KnowledgeIndexer.start() should POST to /bos/subscribe on Agora."""
        from cockpit.web.knowledge_indexer import KnowledgeIndexer

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"subscription_id": "sub-abc-123"}

        with patch("cockpit.web.knowledge_indexer.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            indexer = KnowledgeIndexer(agora_endpoint="http://127.0.0.1:7422")
            await indexer.start()

        assert indexer._running is True
        assert indexer._sub_id == "sub-abc-123"
        mock_client.post.assert_called_once_with(
            "http://127.0.0.1:7422/bos/subscribe",
            json={
                "service": "cockpit-knowledge-indexer",
                "pattern": "bos://brain/events/card_updated",
            },
        )

    @pytest.mark.asyncio
    async def test_start_graceful_when_agora_offline(self):
        """KnowledgeIndexer.start() should not raise when Agora is unreachable."""
        import httpx as real_httpx

        from cockpit.web.knowledge_indexer import KnowledgeIndexer

        with patch("cockpit.web.knowledge_indexer.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=real_httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            indexer = KnowledgeIndexer()
            await indexer.start()  # must not raise

        assert indexer._running is False

    @pytest.mark.asyncio
    async def test_handle_card_updated_calls_kos_upsert(self):
        """handle_card_updated() should POST to KOS upsert endpoint."""
        from cockpit.web.knowledge_indexer import KnowledgeIndexer

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("cockpit.web.knowledge_indexer.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            indexer = KnowledgeIndexer()
            await indexer.handle_card_updated(
                {"slug": "my-note", "title": "My Note", "path": "data/cards/my-note.md", "action": "upsert"}
            )

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "upsert" in str(call_kwargs)
        assert "my-note" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_handle_card_updated_skips_malformed_payload(self):
        """handle_card_updated() should not raise on malformed payload."""
        from cockpit.web.knowledge_indexer import KnowledgeIndexer

        indexer = KnowledgeIndexer()
        # Should not raise; bad payload → just logs a warning
        await indexer.handle_card_updated({"action": "upsert"})
