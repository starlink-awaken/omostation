"""Thread-safe registry of discovered compute nodes.

Provides CRUD operations, filtering, and event notification for the
mesh topology.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from .node import ComputeNode, NodeStatus

_log = logging.getLogger(__name__)

# Type alias for topology change listeners
NodeListener = Callable[[str, ComputeNode], None]


class NodeRegistry:
    """In-memory registry of compute nodes with thread-safe access.

    Maintains a dict of known nodes and provides filtering, iteration,
    and change notification capabilities.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ComputeNode] = {}
        self._lock = threading.RLock()
        self._listeners: list[NodeListener] = []

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def register(self, node: ComputeNode) -> bool:
        """Register or update a node.

        Returns ``True`` if the node was newly added, ``False`` if it
        was an update to an existing entry.
        """
        with self._lock:
            is_new = node.node_id not in self._nodes
            self._nodes[node.node_id] = node
        self._notify("registered" if is_new else "updated", node)
        return is_new

    def unregister(self, node_id: str) -> bool:
        """Remove a node from the registry.

        Returns ``True`` if the node existed and was removed.
        """
        with self._lock:
            node = self._nodes.pop(node_id, None)
        if node:
            self._notify("unregistered", node)
            return True
        return False

    def get(self, node_id: str) -> ComputeNode | None:
        """Look up a node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def get_all(self) -> list[ComputeNode]:
        """Return a snapshot of all registered nodes."""
        with self._lock:
            return list(self._nodes.values())

    def count(self) -> int:
        """Total number of registered nodes."""
        with self._lock:
            return len(self._nodes)

    # ── Filtering ─────────────────────────────────────────────────────────────

    def filter(self, **kwargs: Any) -> list[ComputeNode]:
        """Filter nodes by field values.

        Usage::

            registry.filter(status=NodeStatus.ONLINE)
            registry.filter(network_zone="local", engine_type=NodeEngineType.LOCAL_DAEMON)
        """
        with self._lock:
            results = list(self._nodes.values())
            for attr, value in kwargs.items():
                results = [n for n in results if getattr(n, attr, None) == value]
            return results

    def get_online(self) -> list[ComputeNode]:
        """Shortcut: return all nodes with ONLINE status."""
        return self.filter(status=NodeStatus.ONLINE)

    def get_by_zone(self, zone: str) -> list[ComputeNode]:
        """Shortcut: return nodes in a specific network zone."""
        return self.filter(network_zone=zone)

    def get_by_protocol(self, protocol: str) -> list[ComputeNode]:
        """Shortcut: return nodes supporting a specific protocol."""
        with self._lock:
            return [n for n in self._nodes.values() if protocol in n.protocols]

    # ── Listeners ─────────────────────────────────────────────────────────────

    def add_listener(self, listener: NodeListener) -> None:
        """Register a callback invoked on topology changes.

        The callback receives ``(event_type, node)`` where event_type
        is one of ``"registered"``, ``"updated"``, ``"unregistered"``.
        """
        self._listeners.append(listener)

    def remove_listener(self, listener: NodeListener) -> None:
        """Remove a previously registered listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, event: str, node: ComputeNode) -> None:
        for listener in self._listeners:
            try:
                listener(event, node)
            except Exception:
                _log.exception("NodeRegistry listener failed for event %s", event)

    # ── Bulk operations ───────────────────────────────────────────────────────

    def merge(self, nodes: list[ComputeNode]) -> int:
        """Register a batch of nodes. Returns count of new additions."""
        count = 0
        for node in nodes:
            if self.register(node):
                count += 1
        return count

    def clear(self) -> None:
        """Remove all nodes from the registry."""
        with self._lock:
            self._nodes.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire registry to a dict (for status output)."""
        with self._lock:
            return {
                "count": len(self._nodes),
                "nodes": {nid: node.to_dict() for nid, node in self._nodes.items()},
            }
