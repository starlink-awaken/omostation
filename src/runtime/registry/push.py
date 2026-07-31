"""Agent Registry — Push Trigger for local mutations.

When a node's registry state changes (register/deregister/heartbeat),
this module triggers a push notification to all known peers, ensuring
eventual consistency across the cluster.

Phase 46 W3: Registry push trigger.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

DEFAULT_RETRY_LIMIT = 3
DEFAULT_RETRY_DELAY = 2.0
DEFAULT_PUSH_TIMEOUT = 5


@dataclass
class PushResult:
    """Result of a push attempt to a single peer."""

    peer_id: str
    success: bool
    status_code: int = 0
    error: str = ""
    retries: int = 0

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "success": self.success,
            "status_code": self.status_code,
            "error": self.error,
            "retries": self.retries,
        }


class PushTrigger:
    """Push-triggered synchronizer: on local mutation, POST delta to all peers.

    Unlike GossipSync (pull-based), PushTrigger sends deltas *immediately*
    after a local write, reducing the window for inconsistency.

    Usage:
        trigger = PushTrigger(peers={"node-b": "http://10.0.0.2:8765"})
        await trigger.push_delta({"agents": [...]}, local_node_id="node-a")
    """

    def __init__(
        self,
        peers: dict[str, str] | None = None,
        retry_limit: int = DEFAULT_RETRY_LIMIT,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        timeout: float = DEFAULT_PUSH_TIMEOUT,
    ) -> None:
        self._peers: dict[str, str] = peers or {}
        self._retry_limit = retry_limit
        self._retry_delay = retry_delay
        self._timeout = timeout
        self._push_history: list[PushResult] = []
        self._vclock: int = 0
        self._last_push: float = 0

    # ── Peer management ──────────────────────────────────────────

    def add_peer(self, peer_id: str, base_url: str) -> None:
        self._peers[peer_id] = base_url

    def remove_peer(self, peer_id: str) -> None:
        self._peers.pop(peer_id, None)

    def list_peers(self) -> dict[str, str]:
        return dict(self._peers)

    # ── Push ─────────────────────────────────────────────────────

    async def push_delta(
        self,
        delta: dict,
        local_node_id: str,
    ) -> list[PushResult]:
        """Push a state delta to all known peers (best-effort, concurrent).

        Args:
            delta: Dict containing changed state (agents, nodes, tasks, etc.)
            local_node_id: ID of the originating node.
        """
        self._vclock += 1
        results: list[PushResult] = []

        tasks = [
            self._push_to_peer(peer_id, url, delta, local_node_id)
            for peer_id, url in self._peers.items()
        ]
        if tasks:
            results = list(await asyncio.gather(*tasks, return_exceptions=False))

        self._push_history.extend(results)
        self._last_push = time.time()
        return results

    async def push_register_agent(self, agent_dict: dict, local_node_id: str) -> list[PushResult]:
        """Push an agent registration event."""
        return await self.push_delta(
            {"type": "agent_registered", "agent": agent_dict},
            local_node_id,
        )

    async def push_deregister_agent(self, agent_id: str, local_node_id: str) -> list[PushResult]:
        """Push an agent deregistration event."""
        return await self.push_delta(
            {"type": "agent_deregistered", "agent_id": agent_id},
            local_node_id,
        )

    async def push_heartbeat(self, agent_id: str, local_node_id: str) -> list[PushResult]:
        """Push a heartbeat event."""
        return await self.push_delta(
            {"type": "heartbeat", "agent_id": agent_id},
            local_node_id,
        )

    # ── Internal ─────────────────────────────────────────────────

    async def _push_to_peer(
        self,
        peer_id: str,
        base_url: str,
        delta: dict,
        local_node_id: str,
    ) -> PushResult:
        """Push delta to a single peer with retry."""
        body = {
            "source_node_id": local_node_id,
            "vclock": self._vclock,
            "delta": delta,
        }
        result = PushResult(peer_id=peer_id, success=False)

        for attempt in range(self._retry_limit):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        f"{base_url}/sync/delta", json=body
                    )
                    if resp.status_code < 400:
                        result.success = True
                        result.status_code = resp.status_code
                        result.retries = attempt
                        return result
                    result.status_code = resp.status_code
                    result.retries = attempt + 1
            except (httpx.HTTPError, OSError):
                result.retries = attempt + 1
            if attempt < self._retry_limit - 1:
                await asyncio.sleep(self._retry_delay * (attempt + 1))

        result.error = f"Failed after {self._retry_limit} retries"
        return result

    # ── Status API ───────────────────────────────────────────────

    def get_status(self) -> dict:
        recent = self._push_history[-10:] if self._push_history else []
        success = sum(1 for r in self._push_history if r.success)
        failed = len(self._push_history) - success
        return {
            "peers": len(self._peers),
            "vclock": self._vclock,
            "total_pushes": len(self._push_history),
            "success": success,
            "failed": failed,
            "last_push": self._last_push,
            "recent": [r.to_dict() for r in recent],
        }


__all__ = ["PushTrigger", "PushResult"]