"""G-DEL.1 — Agent registry (in-process multi-node simulation).

Not a multi-datacenter product; models N logical nodes each holding agents.
Used to measure schedule success rate > 99% (BET-7e074).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentRecord:
    agent_id: str
    role_id: str
    node_id: str
    healthy: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    capacity: int = 1
    inflight: int = 0

    def can_accept(self) -> bool:
        return self.healthy and self.inflight < self.capacity


class AgentRegistry:
    """Register / heartbeat / list agents across logical nodes."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}
        self._nodes: set[str] = set()

    def register_node(self, node_id: str) -> str:
        if not node_id or not node_id.strip():
            raise ValueError("node_id required")
        self._nodes.add(node_id)
        return node_id

    def register_agent(
        self,
        *,
        node_id: str,
        role_id: str,
        agent_id: str | None = None,
        capacity: int = 1,
    ) -> AgentRecord:
        if node_id not in self._nodes:
            self.register_node(node_id)
        aid = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        if aid in self._agents:
            raise ValueError(f"agent already registered: {aid}")
        rec = AgentRecord(
            agent_id=aid,
            role_id=role_id,
            node_id=node_id,
            capacity=max(1, capacity),
        )
        self._agents[aid] = rec
        return rec

    def heartbeat(self, agent_id: str, *, healthy: bool = True) -> AgentRecord:
        rec = self._require(agent_id)
        rec.healthy = healthy
        rec.last_heartbeat = time.time()
        return rec

    def mark_unhealthy(self, agent_id: str) -> None:
        self.heartbeat(agent_id, healthy=False)

    def list_agents(self, *, role_id: str | None = None, healthy_only: bool = False) -> list[AgentRecord]:
        out = list(self._agents.values())
        if role_id is not None:
            out = [a for a in out if a.role_id == role_id]
        if healthy_only:
            out = [a for a in out if a.healthy]
        return out

    def acquire_slot(self, agent_id: str) -> bool:
        rec = self._require(agent_id)
        if not rec.can_accept():
            return False
        rec.inflight += 1
        return True

    def release_slot(self, agent_id: str) -> None:
        rec = self._require(agent_id)
        rec.inflight = max(0, rec.inflight - 1)

    def snapshot(self) -> dict[str, Any]:
        return {
            "nodes": sorted(self._nodes),
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "role_id": a.role_id,
                    "node_id": a.node_id,
                    "healthy": a.healthy,
                    "inflight": a.inflight,
                    "capacity": a.capacity,
                }
                for a in self._agents.values()
            ],
        }

    def _require(self, agent_id: str) -> AgentRecord:
        if agent_id not in self._agents:
            raise KeyError(f"unknown agent: {agent_id}")
        return self._agents[agent_id]
