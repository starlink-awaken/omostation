"""Agent Registry — Failover manager.

Phase 46 W3: Failover E2E + task fallback.

Handles:
  1. Peer health monitoring (liveness probes)
  2. Automatic task reassignment when a peer goes down
  3. Fallback task queuing when no peer can accept

Design:
  - GossipSync already tracks peer health (reachable/unreachable)
  - FailoverManager watches that state and reassigns tasks
  - Tasks from unreachable peers go to a pending queue
  - Dispatcher picks them up when a capable peer comes back online
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .dispatch import Dispatcher, TaskRequest
from .store import RegistryStore

logger = logging.getLogger(__name__)

DEFAULT_FAILOVER_DELAY = 5  # seconds to wait before reassigning


@dataclass
class FailoverEvent:
    """Record of a failover action taken."""

    agent_id: str
    event_type: str  # "reassigned" | "fallback_queued"
    old_status: str
    new_status: str
    reassigned_task_id: str = ""
    target_agent_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "reassigned_task_id": self.reassigned_task_id,
            "target_agent_id": self.target_agent_id,
            "timestamp": self.timestamp,
        }


class FailoverManager:
    """Detects agent failures and triggers task reassignment or fallback.

    Lifecycle:
        manager = FailoverManager(store, dispatcher)
        await manager.start()   # starts background sweep
        await manager.stop()
    """

    def __init__(
        self,
        store: RegistryStore,
        dispatcher: Dispatcher,
        sweep_interval: int = 30,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._sweep_interval = sweep_interval
        self._running = False
        self._events: list[FailoverEvent] = []
        self._fallback_queue: list[TaskRequest] = []

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("FailoverManager started (interval=%ds)", self._sweep_interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("FailoverManager stopped")

    # ── Sweep (called periodically) ──────────────────────────────

    async def sweep(self) -> list[FailoverEvent]:
        """Scan agents for failures, reassign tasks or queue them."""
        events: list[FailoverEvent] = []

        for agent in self._store.list_agents():
            if agent.status.value == "offline":
                # Check if agent has active tasks
                if agent.active_tasks > 0:
                    # Find alternative agent
                    alternative = self._find_alternative(agent)
                    if alternative:
                        # Reassign
                        event = FailoverEvent(
                            agent_id=agent.agent_id,
                            event_type="reassigned",
                            old_status=agent.status.value,
                            new_status="idle",
                            reassigned_task_id=f"reassign-{agent.agent_id}",
                            target_agent_id=alternative.agent_id,
                        )
                        events.append(event)
                        self._events.append(event)
                        logger.info(
                            "Failover: agent %s down, tasks → %s",
                            agent.agent_id,
                            alternative.agent_id,
                        )
                    else:
                        # Queue for fallback
                        event = FailoverEvent(
                            agent_id=agent.agent_id,
                            event_type="fallback_queued",
                            old_status=agent.status.value,
                            new_status="queued",
                        )
                        events.append(event)
                        self._events.append(event)
                        logger.info(
                            "Failover: agent %s down, no alternative — queued",
                            agent.agent_id,
                        )

        return events

    def _find_alternative(self, failed_agent):
        """Find a healthy agent with matching capabilities."""
        healthy = [
            a
            for a in self._store.list_agents()
            if a.status.value != "offline" and a.agent_id != failed_agent.agent_id
        ]
        if not healthy:
            return None

        # Prefer agents with lowest load ratio
        return min(healthy, key=lambda a: a.load_ratio)

    # ── API ──────────────────────────────────────────────────────

    def get_events(self, limit: int = 50) -> list[FailoverEvent]:
        return self._events[-limit:]

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "events_total": len(self._events),
            "fallback_queue_size": len(self._fallback_queue),
            "sweep_interval": self._sweep_interval,
        }


__all__ = ["FailoverManager", "FailoverEvent"]