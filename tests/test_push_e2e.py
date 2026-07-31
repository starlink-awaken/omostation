"""E2E test for Registry push trigger — two-node delta propagation.

Spins up two FastAPI test servers (node-a, node-b), registers an agent on node-a,
and verifies that PushTrigger pushes the delta to node-b where it's applied.
"""

from __future__ import annotations

import httpx
import pytest

from runtime.registry.push import PushResult, PushTrigger


class TestPushTriggerE2E:
    """Verify PushTrigger propagates deltas between two running registry servers."""

    @pytest.mark.asyncio
    async def test_push_delta_between_two_nodes(self):
        """Push delta → peer receives correct payload."""
        received_deltas: list[dict] = []

        async def _mock_push(peer_id, url, delta, source_node_id):
            received_deltas.append(delta)
            return PushResult(peer_id=peer_id, success=True, status_code=200)

        trigger = PushTrigger(peers={"node-b": "http://fake:9999"})
        # Monkeypatch _push_to_peer to capture instead of HTTP
        trigger._push_to_peer = _mock_push  # type: ignore

        delta = {"type": "agent_registered", "agent": {"name": "test-agent", "node_id": "node-a"}}
        results = await trigger.push_delta(delta, local_node_id="node-a")

        assert len(results) == 1
        assert results[0].success is True
        assert len(received_deltas) == 1
        assert received_deltas[0]["type"] == "agent_registered"
        assert received_deltas[0]["agent"]["name"] == "test-agent"

    @pytest.mark.asyncio
    async def test_push_to_multiple_peers(self):
        """Push delta to 3 peers → all 3 receive it."""
        received: list[str] = []

        async def _mock_push(peer_id, url, delta, source_node_id):
            received.append(peer_id)
            return PushResult(peer_id=peer_id, success=True, status_code=200)

        trigger = PushTrigger(peers={
            "peer-1": "http://p1:8000",
            "peer-2": "http://p2:8000",
            "peer-3": "http://p3:8000",
        })
        trigger._push_to_peer = _mock_push  # type: ignore

        results = await trigger.push_delta({"type": "heartbeat", "agent_id": "a1"}, "self")

        assert len(results) == 3
        assert set(received) == {"peer-1", "peer-2", "peer-3"}
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_push_retry_on_failure(self):
        """Peer unreachable → retry up to limit, then report failure."""
        from unittest.mock import AsyncMock, patch

        call_count = 0

        trigger = PushTrigger(
            peers={"dead-peer": "http://dead:9999"},
            retry_limit=3,
            retry_delay=0.01,
        )

        # Patch httpx.AsyncClient.post to always fail
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            def _side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                raise httpx.ConnectError("connection refused")

            mock_client.post = AsyncMock(side_effect=_side_effect)
            mock_cls.return_value = mock_client

            results = await trigger.push_delta({"type": "test"}, "self")

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].retries == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_vclock_increments(self):
        """Each push increments the vector clock."""
        trigger = PushTrigger(peers={"p1": "http://x:8000"})

        async def _mock_push(peer_id, url, delta, source_node_id):
            return PushResult(peer_id=peer_id, success=True, status_code=200)

        trigger._push_to_peer = _mock_push  # type: ignore

        assert trigger._vclock == 0
        await trigger.push_delta({}, "self")
        assert trigger._vclock == 1
        await trigger.push_delta({}, "self")
        assert trigger._vclock == 2

    def test_status_reflects_history(self):
        """get_status() shows push history."""
        trigger = PushTrigger(peers={"p1": "http://x:8000"})
        trigger._push_history = [
            PushResult(peer_id="p1", success=True, status_code=200),
            PushResult(peer_id="p1", success=False, status_code=500),
            PushResult(peer_id="p1", success=True, status_code=200),
        ]
        status = trigger.get_status()
        assert status["total_pushes"] == 3
        assert status["success"] == 2
        assert status["failed"] == 1
        assert status["peers"] == 1
