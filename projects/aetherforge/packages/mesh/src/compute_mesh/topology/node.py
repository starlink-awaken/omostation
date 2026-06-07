"""Compute node data model for the AetherForge mesh topology."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NodeStatus(Enum):
    """Lifecycle status of a compute node."""

    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    DRAINING = "draining"


class NodeEngineType(Enum):
    """The kind of compute engine a node represents."""

    LOCAL_DAEMON = "local_daemon"  # e.g. local Ollama
    CLOUD_API = "cloud_api"  # e.g. OpenAI API
    REMOTE_WORKER = "remote_worker"  # remote agent worker
    SSH_TUNNEL = "ssh_tunnel"  # tunneled remote daemon
    EDGE_DEVICE = "edge_device"  # edge compute


@dataclass
class ComputeNode:
    """Describes a single compute node in the mesh.

    Each node is a uniquely identifiable compute resource — typically
    an LLM-serving endpoint (Ollama, OpenAI, etc.) or a remote worker
    that can execute tasks.
    """

    node_id: str
    """Unique identifier (e.g. ``"ollama-mac-mini"``)."""

    name: str = ""
    """Human-readable name."""

    engine_type: NodeEngineType = NodeEngineType.LOCAL_DAEMON
    """What kind of engine this node runs."""

    base_url: str = ""
    """Endpoint URL (e.g. ``http://localhost:11434``)."""

    network_zone: str = "local"
    """Network locality: ``"local"``, ``"lan"``, ``"cloud"``, ``"tunnel"``."""

    protocols: list[str] = field(default_factory=list)
    """Supported API protocols (e.g. ``["openai"]``, ``["anthropic"]``)."""

    capabilities: list[str] = field(default_factory=list)
    """Supported capabilities (e.g. ``["chat", "embedding", "vision"]``)."""

    status: NodeStatus = NodeStatus.UNKNOWN
    """Current operational status."""

    priority: int = 5
    """Selection priority (1=highest, 10=lowest). Useful for static config."""

    cost_per_1k_tokens: dict[str, float] = field(default_factory=lambda: {"input": 0.0, "output": 0.0})
    """Per-token cost in USD (or EU). Updated by CostTracker."""

    avg_latency_ms: float = 0.0
    """Rolling average latency in milliseconds."""

    active_requests: int = 0
    """Currently active request count."""

    max_concurrency: int = 1
    """Maximum concurrent requests this node can handle."""

    last_seen: float = 0.0
    """Unix timestamp of last successful health check."""

    first_seen: float = 0.0
    """Unix timestamp of when this node was discovered."""

    tags: dict[str, str] = field(default_factory=dict)
    """Arbitrary key-value tags for filtering and routing."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Extensible metadata blob."""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.node_id
        now = datetime.now().timestamp()
        if not self.first_seen:
            self.first_seen = now

    @property
    def is_online(self) -> bool:
        return self.status == NodeStatus.ONLINE

    @property
    def load_factor(self) -> float:
        """Utilization ratio (0.0–1.0)."""
        if self.max_concurrency == 0:
            return 1.0
        return min(1.0, self.active_requests / self.max_concurrency)

    @property
    def effective_cost(self) -> float:
        """Weighted cost for quick comparison."""
        return self.cost_per_1k_tokens.get("input", 0) + self.cost_per_1k_tokens.get("output", 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "engine_type": self.engine_type.value,
            "base_url": self.base_url,
            "network_zone": self.network_zone,
            "protocols": self.protocols,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "priority": self.priority,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "avg_latency_ms": self.avg_latency_ms,
            "active_requests": self.active_requests,
            "max_concurrency": self.max_concurrency,
            "load_factor": self.load_factor,
            "last_seen": self.last_seen,
            "tags": self.tags,
        }
