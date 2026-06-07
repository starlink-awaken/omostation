"""ComputePool — resource aggregation, health monitoring, and load management.

The pool sits on top of the topology layer, taking discovered nodes
and providing a unified interface for health-checking, load tracking,
and node selection.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from ..topology import ComputeNode, NodeRegistry, NodeStatus, TopologyScanner

_log = logging.getLogger(__name__)

# Default health-check timeout in seconds
_DEFAULT_HEALTH_TIMEOUT = 5.0

# Type for pool event listeners
PoolListener = Callable[[str, ComputeNode], None]


class ComputePool:
    """Aggregates compute nodes from topology, monitors health and load.

    The pool is the main interface for higher layers (scheduler, API)
    to interact with mesh compute resources.

    Usage::

        pool = ComputePool()
        pool.scan()  # discover nodes via topology scanner
        pool.health_check_all()  # probe all nodes
        online = pool.get_online()
    """

    def __init__(
        self,
        registry: NodeRegistry | None = None,
        scanner: TopologyScanner | None = None,
    ) -> None:
        self._registry = registry or NodeRegistry()
        self._scanner = scanner or TopologyScanner(self._registry)
        self._lock = threading.RLock()
        self._listeners: list[PoolListener] = []
        self._health_history: dict[str, list[dict[str, Any]]] = {}
        self._max_history = 100

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def registry(self) -> NodeRegistry:
        return self._registry

    @property
    def scanner(self) -> TopologyScanner:
        return self._scanner

    @property
    def node_count(self) -> int:
        return self._registry.count()

    # ── Discovery ────────────────────────────────────────────────────────────

    def scan(self) -> list[ComputeNode]:
        """Run full topology discovery and return discovered nodes."""
        return self._scanner.scan_all()

    # ── Health checks ────────────────────────────────────────────────────────

    def health_check_node(self, node_id: str) -> bool:
        """Probe a single node's health.

        Performs a TCP-level port check for local daemons, or a simple
        availability check. Returns ``True`` if the node is reachable.

        Updates the node's status and ``last_seen`` timestamp.
        """
        node = self._registry.get(node_id)
        if node is None:
            return False

        is_alive = self._probe_node(node)
        now = time.time()

        with self._lock:
            entry = self._registry.get(node_id)
            if entry is None:
                return False
            entry.last_seen = now
            old_status = entry.status
            entry.status = NodeStatus.ONLINE if is_alive else NodeStatus.OFFLINE
            if old_status != entry.status:
                self._notify("status_change", entry)
            self._record_health(node_id, is_alive)

        return is_alive

    def health_check_all(self) -> dict[str, bool]:
        """Probe all registered nodes. Returns ``{node_id: is_alive}``."""
        results: dict[str, bool] = {}
        for node in self._registry.get_all():
            results[node.node_id] = self.health_check_node(node.node_id)
        return results

    def _probe_node(self, node: ComputeNode) -> bool:
        """Low-level node probe. Returns True if reachable."""
        from urllib.parse import urlparse

        if not node.base_url:
            # No URL = assume configured but not yet reachable
            return False

        try:
            parsed = urlparse(node.base_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(_DEFAULT_HEALTH_TIMEOUT)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _record_health(self, node_id: str, is_alive: bool) -> None:
        """Record a health check result in the history buffer."""
        if node_id not in self._health_history:
            self._health_history[node_id] = []
        history = self._health_history[node_id]
        history.append({"ts": time.time(), "alive": is_alive})
        # Trim to max history
        if len(history) > self._max_history:
            self._health_history[node_id] = history[-self._max_history :]

    def get_health_history(self, node_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent health check history for a node."""
        history = self._health_history.get(node_id, [])
        return history[-limit:]

    # ── Load tracking ────────────────────────────────────────────────────────

    def assign_request(self, node_id: str) -> bool:
        """Increment active request count for a node.

        Returns ``False`` if the node is at max concurrency.
        """
        node = self._registry.get(node_id)
        if node is None:
            return False
        with self._lock:
            node = self._registry.get(node_id)
            if node is None:
                return False
            if node.active_requests >= node.max_concurrency:
                return False
            node.active_requests += 1
        return True

    def release_request(self, node_id: str) -> bool:
        """Decrement active request count for a node."""
        node = self._registry.get(node_id)
        if node is None:
            return False
        with self._lock:
            node = self._registry.get(node_id)
            if node is None:
                return False
            node.active_requests = max(0, node.active_requests - 1)
        return True

    # ── Selection helpers ────────────────────────────────────────────────────

    def get_online(self) -> list[ComputeNode]:
        """Return all nodes currently marked ONLINE."""
        return self._registry.get_online()

    def get_best_node(self, preferred_zone: str = "") -> ComputeNode | None:
        """Pick the best available node (lowest load, online, highest priority).

        Args:
            preferred_zone: If set, prefer nodes in this network zone.

        Returns:
            The best node, or ``None`` if no online nodes exist.
        """
        candidates = self.get_online()
        if not candidates:
            return None

        # Sort by: zone match → priority → load factor → cost
        def sort_key(n: ComputeNode) -> tuple:
            zone_match = 0 if preferred_zone and n.network_zone == preferred_zone else 1
            return (zone_match, n.priority, n.load_factor, n.effective_cost)

        candidates.sort(key=sort_key)
        return candidates[0]

    # ── Listeners ────────────────────────────────────────────────────────────

    def add_listener(self, listener: PoolListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: PoolListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, event: str, node: ComputeNode) -> None:
        for listener in self._listeners:
            try:
                listener(event, node)
            except Exception:
                _log.exception("Pool listener failed for event %s", event)

    # ── Status report ────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return a full status snapshot of the pool."""
        online = self.get_online()
        all_nodes = self._registry.get_all()
        return {
            "total_nodes": len(all_nodes),
            "online_nodes": len(online),
            "offline_nodes": len(all_nodes) - len(online),
            "nodes": [n.to_dict() for n in all_nodes],
        }

    def get_summary(self) -> dict[str, Any]:
        """Return a compact summary string."""
        online = self.get_online()
        return {
            "total": self.node_count,
            "online": len(online),
            "offline": self.node_count - len(online),
            "zones": list({n.network_zone for n in self._registry.get_all()}),
        }


# Import socket at module level for _probe_node
import socket  # noqa: E402
