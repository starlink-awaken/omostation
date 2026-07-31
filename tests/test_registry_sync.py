"""Unit tests for runtime.registry.sync — Phase 46 W2 GossipSync.

Tests:
  1. Peer — to_dict serialization
  2. SyncResult — stats tracking
  3. GossipSync — peer management
  4. GossipSync — conflict resolution (LWW + tie-break)
  5. GossipSync — sync_once with mocked peers
  6. GossipSync — failover (unreachable peer handling)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runtime.registry.sync import GossipSync, Peer, SyncResult

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_store():
    """Create a mock RegistryStore."""
    store = MagicMock()
    store.list_agents.return_value = []
    store.get_agent.return_value = None
    store.register_agent = MagicMock()
    store.update_agent = MagicMock()
    return store


@pytest.fixture
def sample_agent_dict():
    """Sample agent dict from remote peer."""
    now = datetime.now(UTC).isoformat()
    return {
        "agent_id": "abc123",
        "name": "test-agent",
        "node_id": "node-b",
        "endpoint": "http://node-b:9000",
        "capabilities": [{"name": "python", "tags": [], "cost_eu": 0.0}],
        "status": "idle",
        "max_concurrency": 1,
        "active_tasks": 0,
        "metadata": {},
        "registered_at": now,
        "last_heartbeat": now,
    }


# ── Tests: Peer ──────────────────────────────────────────────


class TestPeer:
    def test_to_dict(self):
        peer = Peer(node_id="node-b", host="10.0.0.2", port=8765)
        d = peer.to_dict()
        assert d["node_id"] == "node-b"
        assert d["host"] == "10.0.0.2"
        assert d["port"] == 8765
        assert d["reachable"] is True
        assert d["consecutive_failures"] == 0

    def test_to_dict_with_last_contact(self):
        peer = Peer(node_id="n1", host="h1", port=8000)
        now = datetime.now(UTC)
        peer.last_contact = now
        d = peer.to_dict()
        assert d["last_contact"] == now.isoformat()

    def test_base_url(self):
        peer = Peer(node_id="n1", host="10.0.0.2", port=8765)
        assert peer.base_url == "http://10.0.0.2:8765"


# ── Tests: SyncResult ────────────────────────────────────────


class TestSyncResult:
    def test_default_values(self):
        r = SyncResult()
        assert r.pulled == 0
        assert r.pushed == 0
        assert r.conflicts_resolved == 0
        assert r.peers_unreachable == 0
        assert r.errors == []

    def test_to_dict(self):
        r = SyncResult(pulled=5, pushed=3, conflicts_resolved=2, peers_unreachable=1, duration_ms=123.4)
        d = r.to_dict()
        assert d["pulled"] == 5
        assert d["pushed"] == 3
        assert d["conflicts_resolved"] == 2
        assert d["peers_unreachable"] == 1
        assert d["duration_ms"] == 123.4


# ── Tests: GossipSync peer management ────────────────────────


class TestGossipSyncPeerManagement:
    def test_add_and_list_peers(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a")
        peer1 = Peer(node_id="node-b", host="h1", port=8000)
        peer2 = Peer(node_id="node-c", host="h2", port=8000)
        sync.add_peer(peer1)
        sync.add_peer(peer2)
        peers = sync.list_peers()
        assert len(peers) == 2

    def test_remove_peer(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a")
        sync.add_peer(Peer(node_id="node-b", host="h", port=8000))
        sync.remove_peer("node-b")
        assert sync.list_peers() == []


# ── Tests: GossipSync conflict resolution ────────────────────


class TestGossipSyncConflictResolution:
    def test_should_override_when_remote_newer(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a")
        now = datetime.now(UTC)
        local_agent = MagicMock(last_heartbeat=now - timedelta(seconds=10))
        remote_agent = MagicMock(last_heartbeat=now)
        assert sync._should_override(local_agent, remote_agent) is True

    def test_should_not_override_when_local_newer(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a")
        now = datetime.now(UTC)
        local_agent = MagicMock(last_heartbeat=now)
        remote_agent = MagicMock(last_heartbeat=now - timedelta(seconds=10))
        assert sync._should_override(local_agent, remote_agent) is False

    def test_tiebreak_prefers_non_offline(self, mock_store):
        """When timestamps are equal, prefer the non-offline status."""
        sync = GossipSync(mock_store, local_node_id="node-a")
        now = datetime.now(UTC)
        local_agent = MagicMock(last_heartbeat=now, status="offline")
        remote_agent = MagicMock(last_heartbeat=now, status="idle")
        assert sync._should_override(local_agent, remote_agent) is True

    def test_tiebreak_keeps_offline(self, mock_store):
        """When both are offline at the same time, don't override."""
        sync = GossipSync(mock_store, local_node_id="node-a")
        now = datetime.now(UTC)
        local_agent = MagicMock(last_heartbeat=now, status="offline")
        remote_agent = MagicMock(last_heartbeat=now, status="offline")
        assert sync._should_override(local_agent, remote_agent) is False


# ── Tests: GossipSync status API ─────────────────────────────


class TestGossipSyncStatus:
    def test_get_status(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a")
        sync.add_peer(Peer(node_id="node-b", host="h", port=8000))
        status = sync.get_status()
        assert status["local_node_id"] == "node-a"
        assert status["vclock"] == 0
        assert status["running"] is False
        assert len(status["peers"]) == 1

    def test_status_after_sync(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a")
        sync._last_sync_result = SyncResult(pulled=5, pushed=3)
        status = sync.get_status()
        assert status["last_sync"]["pulled"] == 5
        assert status["last_sync"]["pushed"] == 3


# ── Tests: GossipSync sync_once ──────────────────────────────


class TestGossipSyncOnce:
    @pytest.mark.asyncio
    async def test_sync_once_no_peers(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a")
        result = await sync.sync_once()
        assert result.pulled == 0
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_sync_once_successful_pull(self, mock_store, sample_agent_dict):
        sync = GossipSync(mock_store, local_node_id="node-a")
        sync.add_peer(Peer(node_id="node-b", host="10.0.0.2", port=8765))

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = [sample_agent_dict]
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b"[]"

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            mock_store.get_agent.return_value = None  # No existing agent
            result = await sync.sync_once()

        assert result.peers_unreachable == 0
        assert mock_store.register_agent.called

    @pytest.mark.asyncio
    async def test_sync_once_handles_unreachable_peer(self, mock_store):
        import httpx

        sync = GossipSync(mock_store, local_node_id="node-a")
        peer = Peer(node_id="node-b", host="unreachable", port=8765)
        sync.add_peer(peer)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            result = await sync.sync_once()

        assert result.peers_unreachable == 1
        assert peer.consecutive_failures == 1
        assert peer.reachable is True  # Only flips to False after 3 failures


# ── Tests: GossipSync lifecycle ──────────────────────────────


class TestGossipSyncLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a", sync_interval=0.1)
        await sync.start()
        assert sync._running is True
        await sync.stop()
        assert sync._running is False

    @pytest.mark.asyncio
    async def test_double_start_is_noop(self, mock_store):
        sync = GossipSync(mock_store, local_node_id="node-a", sync_interval=0.1)
        await sync.start()
        task1 = sync._task
        await sync.start()  # Should not create new task
        assert sync._task is task1
        await sync.stop()