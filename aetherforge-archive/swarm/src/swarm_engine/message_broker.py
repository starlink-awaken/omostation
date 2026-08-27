from __future__ import annotations

import logging
import queue
import threading
from collections import defaultdict
from collections.abc import Callable

from .role_message import RoleMessage

"""
---
Type: Organ
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for organs/D-Execution/organs/communication/message_broker.py'
Tags:
- auto-metadata
Authority: organs/D-Execution/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution_Organ ≡ Task_Executor
# 内涵 ≝ {Execute, Orchestrate, Manage}
# 外延 ≝ {e | e ∈ D-Execution ∧ executes(e, Tasks)}
# 功能 ⊢ {ExecuteTasks, ManageWorkspace, OrchestrateAgents}
# =============================================================================

_log = logging.getLogger(__name__)


class MessageBroker:
    """
    In-memory message broker for role communication.
    Supports Point-to-Point and Pub/Sub (Broadcast).
    """

    def __init__(self) -> None:
        super().__init__()
        self._queues: dict[str, queue.PriorityQueue] = {}  # role_id -> priority_queue
        self._subscribers: dict[str, list[str]] = defaultdict(list)  # topic -> [role_ids]
        self._lock = threading.RLock()
        self._global_listeners: list[Callable[[RoleMessage], None]] = []

    def register_role(self, role_id: str) -> None:
        """Create a mailbox for a role"""
        with self._lock:
            if role_id not in self._queues:
                self._queues[role_id] = queue.PriorityQueue()

    def unregister_role(self, role_id: str) -> None:
        """Remove a role's mailbox"""
        with self._lock:
            if role_id in self._queues:
                del self._queues[role_id]

    def send(self, message: RoleMessage) -> bool:
        """
        Send a message.
        If target is None, treats as Broadcast (to all registered roles or specific logic).
        For now, let's treat target=None as "System Broadcast" to all.
        """
        # Notify global listeners (e.g. audit logger)
        for listener in self._global_listeners:
            try:
                listener(message)
            except (TypeError, ValueError, AttributeError):
                _log.debug("Global listener raised an exception", exc_info=True)

        if message.target_role_id:
            # Point-to-Point
            return self._deliver(message.target_role_id, message)
        else:
            # Broadcast to all registered roles
            # (In a real system, this might be filtered by topic)
            with self._lock:
                targets = list(self._queues.keys())

            success = True
            for target in targets:
                # Don't send back to sender
                if target != message.sender_role_id:
                    if not self._deliver(target, message):
                        success = False
            return success

    def _deliver(self, target_id: str, message: RoleMessage) -> bool:
        """Internal delivery logic"""
        with self._lock:
            q = self._queues.get(target_id)
            if not q:
                return False

            # PriorityQueue uses (priority, item).
            # We negate priority value because PriorityQueue is Min-Heap (lowest first),
            # but our Enum has High > Low. So we want High (3) to be popped before Low (0).
            # Wait, standard PriorityQueue pops lowest value first.
            # So Priority 0 comes before Priority 3.
            # If we want High Priority (3) first, we should store as -3.

            prio_val = -message.priority.value
            q.put((prio_val, message))
            return True

    def receive(self, role_id: str, timeout: float | None = None) -> RoleMessage | None:
        """
        Receive next message for a role.
        Blocking with timeout.
        """
        # We need to get the queue safely
        # But queue.get is blocking, so we shouldn't hold _lock during get()
        q = None
        with self._lock:
            q = self._queues.get(role_id)

        if not q:
            return None

        try:
            _, message = q.get(timeout=timeout)
            return message
        except queue.Empty:
            return None

    def add_global_listener(self, callback: Callable[[RoleMessage], None]) -> None:
        """Add a listener for all messages (e.g. for logging/debugging)"""
        self._global_listeners.append(callback)
