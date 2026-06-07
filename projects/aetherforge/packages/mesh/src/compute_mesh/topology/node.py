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
class TopologyLabels:
    """Four-layer topology positioning for a compute node.

    Mirrors Kubernetes topology.kubernetes.io conventions:
      - **region**: Geographic region (e.g. ``"us-east-1"``, ``"cn-beijing"``)
      - **zone**: Availability zone within region (e.g. ``"us-east-1a"``)
      - **rack**: Physical or virtual rack (e.g. ``"rack-01"``, ``"local"``)
      - **host**: The hostname or machine identifier (e.g. ``"macmini.local"``)

    Nodes with empty labels match any topology query.
    """

    region: str = ""
    """Geographic region (e.g. ``"us-east-1"``, ``"cn-beijing"``)."""

    zone: str = ""
    """Availability zone (e.g. ``"us-east-1a"``, ``"home"``)."""

    rack: str = ""
    """Physical or virtual rack identifier."""

    host: str = ""
    """Hostname or machine identifier."""

    def matches(self, other: TopologyLabels) -> bool:
        """Check if this node matches *other* at all non-empty levels."""
        if other.region and self.region and self.region != other.region:
            return False
        if other.zone and self.zone and self.zone != other.zone:
            return False
        if other.rack and self.rack and self.rack != other.rack:
            return False
        if other.host and self.host and self.host != other.host:
            return False
        return True

    def affinity_score(self, other: TopologyLabels) -> float:
        """Compute a 0.0–1.0 affinity score.

        The more topology levels match, the higher the score.
        Each matching level adds 0.25; exact match = 1.0.
        """
        score = 0.0
        if other.region and self.region:
            score += 0.25 if self.region == other.region else -0.1
        if other.zone and self.zone:
            score += 0.25 if self.zone == other.zone else -0.1
        if other.rack and self.rack:
            score += 0.25 if self.rack == other.rack else -0.1
        if other.host and self.host:
            score += 0.25 if self.host == other.host else -0.1
        return max(0.0, min(1.0, score))

    def to_dict(self) -> dict[str, str]:
        return {"region": self.region, "zone": self.zone, "rack": self.rack, "host": self.host}


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

    topology: TopologyLabels = field(default_factory=TopologyLabels)
    """Four-layer topology labels (region/zone/rack/host)."""

    network_zone: str = ""
    """Network locality: ``"local"``, ``"lan"``, ``"cloud"``, ``"tunnel"``.
    
    If empty, derived from topology: region != '' → cloud, rack == 'local' → local.
    """

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
        # Auto-derive network_zone from topology if not set
        if not self.network_zone:
            if self.topology.host:
                self.network_zone = "local"
            elif self.topology.region:
                self.network_zone = "cloud"
            else:
                self.network_zone = "local"

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
            "topology": self.topology.to_dict(),
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
