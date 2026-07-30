"""Unified Agent Registry — data models for multi-machine agent coordination.

Merges the best of three existing registries:
- Agora agent_registry: Ed25519 identity, heartbeat TTL, zombie detection
- eCOS agent_registry: AgentStatus enum, node_id, capability-based discovery
- Runtime agent_hub: endpoint tracking, simplicity
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


class AgentStatus(str, enum.Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"
    DRAINING = "draining"
    REMOTE_OFFLINE = "remote_offline"


class NodeRole(str, enum.Enum):
    MASTER = "master"
    WORKER = "worker"
    FUNCTION = "function"


@dataclass
class Capability:
    name: str
    tags: list[str] = field(default_factory=list)
    cost_eu: float = 0.0

    def matches(self, query: str) -> bool:
        q = query.lower()
        return q in self.name.lower() or any(q in t.lower() for t in self.tags)

    def to_dict(self) -> dict:
        return {"name": self.name, "tags": self.tags, "cost_eu": self.cost_eu}

    @classmethod
    def from_dict(cls, d: dict) -> Capability:
        return cls(name=d["name"], tags=d.get("tags", []), cost_eu=d.get("cost_eu", 0.0))


@dataclass
class NodeInfo:
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    host: str = ""
    port: int = 8000
    mcp_port: int = 0
    role: NodeRole = NodeRole.WORKER
    capabilities: list[Capability] = field(default_factory=list)
    load_score: float = 0.0
    health: str = "GREEN"
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "mcp_port": self.mcp_port,
            "role": self.role.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "load_score": self.load_score,
            "health": self.health,
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> NodeInfo:
        caps = [Capability.from_dict(c) for c in d.get("capabilities", [])]
        return cls(
            node_id=d["node_id"],
            host=d["host"],
            port=d.get("port", 8000),
            mcp_port=d.get("mcp_port", 0),
            role=NodeRole(d.get("role", "worker")),
            capabilities=caps,
            load_score=d.get("load_score", 0.0),
            health=d.get("health", "GREEN"),
            last_heartbeat=datetime.fromisoformat(d["last_heartbeat"]),
        )


@dataclass
class AgentInfo:
    agent_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    node_id: str = ""
    endpoint: str = ""
    capabilities: list[Capability] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    max_concurrency: int = 1
    active_tasks: int = 0
    metadata: dict = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def load_ratio(self) -> float:
        if self.max_concurrency <= 0:
            return 1.0
        return min(1.0, self.active_tasks / self.max_concurrency)

    def can_handle(self, required_capabilities: list[str]) -> bool:
        agent_caps = {c.name.lower() for c in self.capabilities}
        agent_tags = {t.lower() for c in self.capabilities for t in c.tags}
        all_known = agent_caps | agent_tags
        return all(q.lower() in all_known for q in required_capabilities)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "node_id": self.node_id,
            "endpoint": self.endpoint,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "status": self.status.value,
            "max_concurrency": self.max_concurrency,
            "active_tasks": self.active_tasks,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentInfo:
        caps = [Capability.from_dict(c) for c in d.get("capabilities", [])]
        return cls(
            agent_id=d["agent_id"],
            name=d.get("name", ""),
            node_id=d.get("node_id", ""),
            endpoint=d.get("endpoint", ""),
            capabilities=caps,
            status=AgentStatus(d.get("status", "idle")),
            max_concurrency=d.get("max_concurrency", 1),
            active_tasks=d.get("active_tasks", 0),
            metadata=d.get("metadata", {}),
            registered_at=datetime.fromisoformat(d["registered_at"]),
            last_heartbeat=datetime.fromisoformat(d["last_heartbeat"]),
        )


__all__ = [
    "AgentInfo",
    "AgentStatus",
    "Capability",
    "NodeInfo",
    "NodeRole",
]
