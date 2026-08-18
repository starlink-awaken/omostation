"""Worker profile definitions for D_Execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BaseWorkerProfile:
    """Base profile describing a worker's identity, capabilities, and
    configuration.

    Profiles are loaded from configuration and can be used to seed worker
    instances with predefined settings.  The ``to_dict()`` output can be
    merged into a worker's config dict during initialisation (see
    ``universal_worker.py``).
    """

    worker_id: str
    persona: str = "Generic Worker"
    archetype: str = ""
    capabilities: list[str] = field(default_factory=list)
    max_concurrency: int = 1
    trust_score: int = 50
    handler_type: str = "mcp_bridge"
    endpoint: str = ""
    heartbeat_interval: float = 10.0
    poll_interval: float = 2.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to a dictionary for config merging."""
        return {
            "worker_id": self.worker_id,
            "persona": self.persona,
            "archetype": self.archetype,
            "capabilities": self.capabilities,
            "max_concurrency": self.max_concurrency,
            "trust_score": self.trust_score,
            "handler_type": self.handler_type,
            "endpoint": self.endpoint,
            "heartbeat_interval": self.heartbeat_interval,
            "poll_interval": self.poll_interval,
            "tags": self.tags,
            "metadata": self.metadata,
        }
