"""Unit tests for runtime.registry.push — PushTrigger module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runtime.registry.push import PushResult, PushTrigger


class TestPushResult:
    def test_to_dict(self):
        r = PushResult(peer_id="node-b", success=True, status_code=200, retries=1)
        d = r.to_dict()
        assert d["peer_id"] == "node-b"
        assert d["success"] is True
        assert d["status_code"] == 200

    def test_default_values(self):
        r = PushResult(peer_id="node-b", success=False)
        assert r.status_code == 0
        assert r.retries == 0


class TestPushTriggerPeerManagement:
    def test_add_remove(self):
        trigger = PushTrigger()
        trigger.add_peer("node-b", "http://10.0.0.2:8765")
        assert "node-b" in trigger.list_peers()
        trigger.remove_peer("node-b")
        assert "node-b" not in trigger.list_peers()


class TestPushTriggerDelta:
    @pytest.mark.asyncio
    async def test_push_delta_no_peers(self):
        trigger = PushTrigger()
        results = await trigger.push_delta({"type": "test"}, "node-a")
        assert results == []
        assert trigger._vclock == 1

    @pytest.mark.asyncio
    async def test_push_register_agent(self):
        trigger = PushTrigger(peers={"node-b": "http://10.0.0.2:8765"})
        with patch("httpx.AsyncClient") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.content = b"[]"
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client

            results = await trigger.push_register_agent(
                {"agent_id": "a1", "name": "test"}, "node-a"
            )
            assert len(results) == 1
            assert results[0].success is True


class TestPushTriggerStatus:
    def test_status_no_history(self):
        trigger = PushTrigger(peers={"n1": "http://a", "n2": "http://b"})
        s = trigger.get_status()
        assert s["peers"] == 2
        assert s["total_pushes"] == 0


class TestPushTriggerRetry:
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        trigger = PushTrigger(
            peers={"node-b": "http://10.0.0.2:8765"},
            retry_limit=2,
            retry_delay=0.01,
        )
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            import httpx as _httpx
            mock_client.post = AsyncMock(side_effect=_httpx.ConnectError("network"))
            mock_cls.return_value = mock_client

            results = await push_delta_safe(trigger, "node-a")

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].retries == 2


async def push_delta_safe(trigger, node_id):
    """Helper to await push_delta."""
    return await trigger.push_delta({}, node_id)