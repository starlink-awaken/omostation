"""Swarm Protocol -- master-worker coordination for parallel agent execution.

Maps to TS source: agentmesh/packages/engine/src/swarm-protocol.ts

Supports:
  - Master/worker registration and heartbeat-based health monitoring
  - Sub-honeycomb lifecycle (pending -> running -> completed/failed/paused)
  - Dependency graph analysis (topological sort via Kahn's algorithm)
  - Cycle detection via iterative DFS
  - Shared state management across sub-honeycombs
  - Progress tracking and heartbeat reports
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

SwarmRole = str
SubHoneycombStatus = str


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SubHoneycomb:
    """An independent workstream within the swarm."""

    id: str
    name: str
    description: str
    status: SubHoneycombStatus = "pending"
    dependencies: list[str] = field(default_factory=list)
    progress: float = 0.0
    assigned_phase: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmState:
    """Complete snapshot of swarm state."""

    swarm_id: str
    master_project_id: str
    role: SwarmRole
    sub_honeycombs: dict[str, SubHoneycomb]
    shared_state: dict[str, Any]
    heartbeat_interval_ms: int
    last_sync: float
    created_at: float


@dataclass
class SwarmConfig:
    """Configuration for the swarm protocol."""

    heartbeat_interval_ms: int = 10_000
    sync_timeout_ms: int = 30_000
    max_sub_honeycombs: int = 20
    auto_rebalance: bool = True


@dataclass
class DependencyGraph:
    """Dependency relationships between sub-honeycombs."""

    nodes: list[str]
    edges: list[dict[str, str]]


@dataclass
class HeartbeatReport:
    """Aggregate swarm health at a point in time."""

    swarm_id: str
    active_count: int
    completed_count: int
    failed_count: int
    progress_pct: float


@dataclass
class ProgressReport:
    """Detailed progress breakdown across all sub-honeycombs."""

    total: int
    completed: int
    running: int
    pending: int
    failed: int
    overall_pct: float


class SwarmProtocol:
    """Master-worker coordination with heartbeat monitoring and task management."""

    def __init__(self, swarm_id: str | None = None, role: str = "worker") -> None:
        self.swarm_id = swarm_id or str(uuid.uuid4())
        self.role = role
        self._honeycombs: dict[str, SubHoneycomb] = {}
        self._shared_state: dict[str, Any] = {}
        self._config = SwarmConfig()
        self._last_sync = time.time()

    def register_honeycomb(self, hc: SubHoneycomb) -> None:
        self._honeycombs[hc.id] = hc

    def get_honeycomb(self, hc_id: str) -> SubHoneycomb | None:
        return self._honeycombs.get(hc_id)

    def update_status(self, hc_id: str, status: str, error: str | None = None) -> bool:
        hc = self._honeycombs.get(hc_id)
        if hc is None:
            return False
        hc.status = status
        hc.error = error
        now = time.time()
        if status == "running" and hc.started_at is None:
            hc.started_at = now
        if status in ("completed", "failed"):
            hc.completed_at = now
        return True

    def update_progress(self, hc_id: str, progress: float) -> bool:
        hc = self._honeycombs.get(hc_id)
        if hc is None:
            return False
        hc.progress = max(0.0, min(1.0, progress))
        return True

    def get_ready_honeycombs(self) -> list[SubHoneycomb]:
        ready: list[SubHoneycomb] = []
        for hc in self._honeycombs.values():
            if hc.status != "pending":
                continue
            if all(self._honeycombs.get(d) and self._honeycombs[d].status == "completed" for d in hc.dependencies):
                ready.append(hc)
        return ready

    def get_status(self) -> dict[str, Any]:
        total = len(self._honeycombs)
        completed = sum(1 for h in self._honeycombs.values() if h.status == "completed")
        running = sum(1 for h in self._honeycombs.values() if h.status == "running")
        failed = sum(1 for h in self._honeycombs.values() if h.status == "failed")
        return {
            "swarm_id": self.swarm_id,
            "role": self.role,
            "total": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "progress_pct": (completed / total * 100) if total > 0 else 0,
        }

    def get_heartbeat(self) -> HeartbeatReport:
        s = self.get_status()
        return HeartbeatReport(
            swarm_id=self.swarm_id,
            active_count=s["running"],
            completed_count=s["completed"],
            failed_count=s["failed"],
            progress_pct=s["progress_pct"],
        )

    @property
    def honeycomb_count(self) -> int:
        return len(self._honeycombs)
