"""Tests for KnowledgeIndexer consumer (ADR-0294).

覆盖：
- callback endpoint 正确处理 card_updated 事件
- callback endpoint 忽略非 card_updated 事件
- 非法 payload 返回 400
- api_knowledge PUT 触发事件发射路径（mock）
- KnowledgeIndexer 启停 lifecycle
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, Response

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def callback_app():
    """返回只挂载了 callback_router 的最小 FastAPI 应用."""
    from cockpit.web.knowledge_indexer import callback_router

    app = FastAPI()
    app.include_router(callback_router)
    return app


@pytest.fixture
def callback_client(callback_app):
    return TestClient(callback_app)


# ─── callback endpoint 测试 ───────────────────────────────────────────────────


def test_callback_ignores_unknown_event_type(callback_client):
    """非 card_updated 事件静默忽略，返回 ok + action=ignored."""
    resp = callback_client.post(
        "/api/knowledge/indexer/callback",
        json={"type": "some:other:event", "data": {"foo": "bar"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["action"] == "ignored"


def test_callback_invalid_payload_returns_400(callback_client):
    """非 dict payload 返回 400."""
    resp = callback_client.post(
        "/api/knowledge/indexer/callback",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in (400, 422)


def test_callback_card_updated_queues_upsert(callback_client):
    """card_updated 事件（legacy brain URI）→ 返回 ok + action=upsert_queued."""
    with patch("cockpit.web.knowledge_indexer._upsert_card", new_callable=AsyncMock):
        resp = callback_client.post(
            "/api/knowledge/indexer/callback",
            json={
                "type": "bos://brain/events/card_updated",
                "data": {"slug": "test-card", "title": "Test Card", "action": "upsert"},
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body.get("action") == "upsert_queued"
    assert body.get("slug") == "test-card"


def test_callback_memory_domain_card_updated_queues_upsert(callback_client):
    """canonical memory-domain card_updated also accepted (ADR-0372 dual-accept)."""
    with patch("cockpit.web.knowledge_indexer._upsert_card", new_callable=AsyncMock):
        resp = callback_client.post(
            "/api/knowledge/indexer/callback",
            json={
                "type": "bos://memory/events/card_updated",
                "data": {"slug": "mem-card", "title": "Mem Card", "action": "upsert"},
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body.get("action") == "upsert_queued"
    assert body.get("slug") == "mem-card"


def test_callback_card_updated_empty_slug(callback_client):
    """slug 为空时不触发 upsert，但不报错."""
    resp = callback_client.post(
        "/api/knowledge/indexer/callback",
        json={"type": "bos://brain/events/card_updated", "data": {}},
    )
    assert resp.status_code == 200


# ─── api_knowledge 事件发射路径测试 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_knowledge_event_uses_v1_tools_call():
    """_notify_knowledge_event 必须调用 /v1/tools/call 而非 /bos/emit."""
    captured = {}

    async def mock_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["body"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        return mock_resp

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = mock_post
        mock_client_cls.return_value = mock_client

        from cockpit.web.api_knowledge import _notify_knowledge_event

        await _notify_knowledge_event(
            "bos://brain/events/card_updated",
            {"slug": "my-card", "title": "My Card", "path": "/data/cards/my-card.md", "action": "upsert"},
        )

    assert "/v1/tools/call" in captured.get("url", ""), (
        f"Expected /v1/tools/call but got: {captured.get('url')}"
    )
    assert captured.get("body", {}).get("tool") == "publish_event"
    assert captured.get("body", {}).get("arguments", {}).get("event_type") == "bos://brain/events/card_updated"


@pytest.mark.asyncio
async def test_notify_knowledge_event_graceful_on_agora_offline():
    """Agora 离线时 _notify_knowledge_event 静默降级，不抛异常."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client_cls.return_value = mock_client

        from cockpit.web.api_knowledge import _notify_knowledge_event

        # Should NOT raise
        await _notify_knowledge_event("bos://brain/events/card_updated", {"slug": "x"})


# ─── KnowledgeIndexer lifecycle 测试 ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_stop_knowledge_indexer_no_crash():
    """start/stop lifecycle 在 Agora 离线时也不崩溃."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("agora offline"))
        mock_client_cls.return_value = mock_client

        from cockpit.web import knowledge_indexer

        await knowledge_indexer.start_knowledge_indexer()
        await asyncio.sleep(0.05)  # let tasks schedule
        await knowledge_indexer.stop_knowledge_indexer()


@pytest.mark.asyncio
async def test_register_subscription_calls_subscribe_event_tool():
    """_register_subscription dual-subscribes memory + brain card_updated patterns."""
    captured_calls: list[dict] = []

    async def mock_post(url, json=None, **kwargs):
        captured_calls.append({"url": url, "body": json})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = lambda: {
            "status": "ok",
            "result": {"subscription_id": "sub_abc123"},
        }
        return mock_resp

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = mock_post
        mock_client_cls.return_value = mock_client

        from cockpit.web import knowledge_indexer

        knowledge_indexer._subscription_id = None
        await knowledge_indexer._register_subscription()

    assert captured_calls, "expected subscribe posts"
    assert all("/v1/tools/call" in c.get("url", "") for c in captured_calls)
    patterns = [
        c.get("body", {}).get("arguments", {}).get("pattern", "")
        for c in captured_calls
        if c.get("body", {}).get("tool") == "subscribe_event"
    ]
    assert "bos://memory/events/card_updated" in patterns
    assert "bos://brain/events/card_updated" in patterns
    assert knowledge_indexer._subscription_id == "sub_abc123"
