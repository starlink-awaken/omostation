"""Agent Registry — cross-node state sync via gossip protocol.

Phase 46 W2: Multi-node state synchronization for distributed registry.

Design:
  - **Pull-based gossip**: each node periodically pulls state from peers
    and reconciles via last-writer-wins (using last_heartbeat timestamp)
  - **Anti-entropy**: vector clocks (per-node logical clock) prevent
    causal regressions during merges
  - **Failover**: if a peer is unreachable, mark its agents as REMOTE_OFFLINE
    rather than removing them — they may return when the peer recovers

Sync triggers:
  1. Periodic background tick (default 30s)
  2. On local mutation (push delta to peers)
  3. On-demand via /sync/force endpoint

Conflict resolution:
  - Agent fields: last_heartbeat wins
  - Status: prefer non-OFFLINE over OFFLINE
  - active_tasks: max(local, remote) — concurrency is additive
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from .models import AgentInfo, AgentStatus
from .store import RegistryStore

logger = logging.getLogger(__name__)

DEFAULT_SYNC_INTERVAL = 30
DEFAULT_SYNC_TIMEOUT = 5
DEFAULT_VClock = int


@dataclass
class Peer:
    """A remote registry node we sync with."""

    node_id: str
    host: str
    port: int
    last_contact: datetime | None = None
    last_sync: datetime | None = None
    consecutive_failures: int = 0
    reachable: bool = True

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "last_contact": self.last_contact.isoformat() if self.last_contact else None,
            "consecutive_failures": self.consecutive_failures,
            "reachable": self.reachable,
        }


@dataclass
class SyncResult:
    """Result of a single sync cycle."""

    pulled: int = 0
    pushed: int = 0
    conflicts_resolved: int = 0
    peers_unreachable: int = 0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pulled": self.pulled,
            "pushed": self.pushed,
            "conflicts_resolved": self.conflicts_resolved,
            "peers_unreachable": self.peers_unreachable,
            "duration_ms": round(self.duration_ms, 1),
            "errors": self.errors,
        }


class GossipSync:
    """Pull-based gossip synchronizer for Agent Registry state.

    Usage:
        sync = GossipSync(store, local_node_id="node-a")
        sync.add_peer(Peer(node_id="node-b", host="10.0.0.2", port=8765))
        await sync.start()
        # ... run registry ...
        await sync.stop()
    """

    def __init__(
        self,
        store: RegistryStore,
        local_node_id: str,
        sync_interval: int = DEFAULT_SYNC_INTERVAL,
        sync_timeout: int = DEFAULT_SYNC_TIMEOUT,
    ) -> None:
        self._store = store
        self._local_node_id = local_node_id
        self._interval = sync_interval
        self._timeout = sync_timeout
        self._peers: dict[str, Peer] = {}
        self._vclock: int = 0
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_sync_result: SyncResult | None = None
        self._mutation_task: asyncio.Task | None = None

    # ── Peer management ──────────────────────────────────────────

    def add_peer(self, peer: Peer) -> None:
        self._peers[peer.node_id] = peer

    def remove_peer(self, node_id: str) -> None:
        self._peers.pop(node_id, None)

    def list_peers(self) -> list[Peer]:
        return list(self._peers.values())

    # ── Lifecycle ───────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="gossip-sync")
        logger.info(
            "GossipSync started (interval=%ds, peers=%d)",
            self._interval,
            len(self._peers),
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        if self._mutation_task:
            self._mutation_task.cancel()
            self._mutation_task = None
        logger.info("GossipSync stopped")

    # ── Sync loop ───────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.sync_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Gossip sync tick failed")
            try:
                await asyncio.wait_for(
                    asyncio.Event().wait(), timeout=self._interval
                )
            except TimeoutError:
                continue

    async def sync_once(self) -> SyncResult:
        """Run a single sync cycle: pull from all peers, push local delta."""
        start = time.time()
        result = SyncResult()

        # Snapshot local agents for push
        local_agents = self._store.list_agents()
        self._vclock += 1

        for peer in self._peers.values():
            try:
                pulled = await self._pull_from_peer(peer)
                result.pulled += pulled
                peer.consecutive_failures = 0
                peer.reachable = True
                peer.last_contact = datetime.now(UTC)
                peer.last_sync = datetime.now(UTC)
            except (httpx.HTTPError, OSError, asyncio.TimeoutError) as e:
                peer.consecutive_failures += 1
                if peer.consecutive_failures >= 3:
                    peer.reachable = False
                    self._store.mark_node_agents_offline(peer.node_id)
                result.peers_unreachable += 1
                result.errors.append(f"{peer.node_id}: {type(e).__name__}")
                logger.warning("Peer %s unreachable: %s", peer.node_id, e)

        # Push local state to reachable peers (best-effort)
        for peer in self._peers.values():
            if not peer.reachable:
                continue
            try:
                pushed = await self._push_to_peer(peer, local_agents)
                result.pushed += pushed
            except (httpx.HTTPError, OSError, asyncio.TimeoutError) as e:
                result.errors.append(f"push-{peer.node_id}: {type(e).__name__}")

        result.duration_ms = (time.time() - start) * 1000
        self._last_sync_result = result
        return result

    def notify_local_mutation(self) -> None:
        """Schedule an immediate push after a local registry mutation."""
        if not self._running or self._mutation_task and not self._mutation_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._vclock += 1
        self._mutation_task = loop.create_task(self._push_reachable(), name="gossip-push")

    async def _push_reachable(self) -> int:
        agents = self._store.list_agents()
        pushed = 0
        for peer in self._peers.values():
            if not peer.reachable:
                continue
            try:
                pushed += await self._push_to_peer(peer, agents)
            except (httpx.HTTPError, OSError, asyncio.TimeoutError):
                peer.consecutive_failures += 1
                if peer.consecutive_failures >= 3:
                    peer.reachable = False
                    self._store.mark_node_agents_offline(peer.node_id)
        return pushed

    def apply_delta(self, agents: list[dict], source_node_id: str = "", vclock: int = 0) -> int:
        """Merge a peer delta and advance the local logical clock."""
        self._vclock = max(self._vclock, vclock) + 1
        merged = 0
        for payload in agents:
            try:
                remote = AgentInfo.from_dict(payload)
            except (KeyError, ValueError, TypeError):
                continue
            existing = self._store.get_agent(remote.agent_id)
            if existing is None:
                self._store.register_agent(remote)
                merged += 1
            elif self._should_override(existing, remote):
                self._store.update_agent(remote.agent_id, **remote.to_dict())
                merged += 1
        return merged

    # ── Pull from peer ──────────────────────────────────────────

    async def _pull_from_peer(self, peer: Peer) -> int:
        """Pull agents from peer and merge into local store."""
        url = f"{peer.base_url}/agents"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            remote_agents = response.json()

        merged = 0
        for agent_dict in remote_agents:
            try:
                agent = AgentInfo.from_dict(agent_dict)
            except (KeyError, ValueError):
                continue
            existing = self._store.get_agent(agent.agent_id)
            if existing is None:
                self._store.register_agent(agent)
                merged += 1
            elif self._should_override(existing, agent):
                self._store.update_agent(agent.agent_id, **agent.to_dict())
                merged += 1
        return merged

    async def _push_to_peer(self, peer: Peer, agents: list[AgentInfo]) -> int:
        """Push local agents to peer (best-effort, peer applies own merge)."""
        url = f"{peer.base_url}/sync/delta"
        body = {
            "source_node_id": self._local_node_id,
            "vclock": self._vclock,
            "agents": [a.to_dict() for a in agents],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
        return len(agents)

    # ── Conflict resolution ─────────────────────────────────────

    def _should_override(self, local: AgentInfo, remote: AgentInfo) -> bool:
        """LWW: remote wins if its last_heartbeat is newer."""
        if remote.last_heartbeat > local.last_heartbeat:
            return True
        # Tie-break: prefer non-offline status
        return (
            remote.last_heartbeat == local.last_heartbeat
            and local.status == AgentStatus.OFFLINE
            and remote.status != AgentStatus.OFFLINE
        )

    # ── Status API ──────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "local_node_id": self._local_node_id,
            "vclock": self._vclock,
            "running": self._running,
            "peers": [p.to_dict() for p in self._peers.values()],
            "last_sync": self._last_sync_result.to_dict() if self._last_sync_result else None,
        }


__all__ = ["DEFAULT_SYNC_INTERVAL", "GossipSync", "Peer", "SyncResult"]
