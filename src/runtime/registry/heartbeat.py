"""Agent Registry — heartbeat liveness manager with zombie detection."""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime, timedelta

from .models import AgentStatus
from .store import RegistryStore

logger = logging.getLogger(__name__)

DEFAULT_TTL = 60
DEFAULT_ZOMBIE = 3600
DEFAULT_INTERVAL = 10


class HeartbeatManager:
    def __init__(self, store: RegistryStore, heartbeat_ttl: int = DEFAULT_TTL, zombie_threshold: int = DEFAULT_ZOMBIE, check_interval: int = DEFAULT_INTERVAL) -> None:
        self._store = store
        self._ttl = timedelta(seconds=heartbeat_ttl)
        self._zombie = timedelta(seconds=zombie_threshold)
        self._interval = check_interval
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="heartbeat-mgr")
        self._thread.start()
        logger.info("HeartbeatManager started (ttl=%ds, zombie=%ds)", self._ttl.total_seconds(), self._zombie.total_seconds())

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._interval + 1)

    def sweep(self) -> dict:
        now = datetime.now(UTC)
        actions = {"marked_offline": [], "removed_zombies": [], "nodes_offline": []}
        for agent in self._store.list_agents():
            age = now - agent.last_heartbeat
            if agent.status != AgentStatus.OFFLINE and age > self._ttl:
                self._store.update_agent(agent.agent_id, status=AgentStatus.OFFLINE)
                actions["marked_offline"].append(agent.agent_id)
            elif agent.status == AgentStatus.OFFLINE and age > self._zombie:
                self._store.remove_agent(agent.agent_id)
                actions["removed_zombies"].append(agent.agent_id)
        for node in self._store.list_nodes():
            age = now - node.last_heartbeat
            if age > self._ttl and node.health != "RED":
                node.health = "RED"
                actions["nodes_offline"].append(node.node_id)
        return actions

    def _loop(self) -> None:
        while self._running:
            try:
                self.sweep()
            except Exception:
                logger.exception("Heartbeat sweep failed")
            time.sleep(self._interval)


__all__ = ["HeartbeatManager"]
