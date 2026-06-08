"""Agent Hub — agent registration, discovery, and lifecycle management.

Provides an in-memory registry for agents with capability-based discovery.
No external dependencies beyond the Python 3.10+ standard library.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class AgentInfo:
    """Immutable record describing a registered agent."""

    id: str
    name: str
    capabilities: list[str]
    endpoint: str
    status: str = "active"
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AgentHub:
    """In-memory agent registry with capability-based discovery."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}

    def register_agent(self, name: str, capabilities: list[str], endpoint: str) -> str:
        agent_id = uuid.uuid4().hex
        info = AgentInfo(
            id=agent_id,
            name=name,
            capabilities=list(capabilities),
            endpoint=endpoint,
        )
        self._agents[agent_id] = info
        return agent_id

    def discover_agents(self, capability: str | None = None) -> list[AgentInfo]:
        if capability is None:
            return list(self._agents.values())
        return [a for a in self._agents.values() if capability in a.capabilities]

    def deregister_agent(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def list_all(self) -> list[AgentInfo]:
        return list(self._agents.values())


__all__ = (
    "AgentHub",
    "AgentInfo",
)
