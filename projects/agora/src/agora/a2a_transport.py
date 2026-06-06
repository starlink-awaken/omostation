from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# A2a Transport ≡ Module
# 内涵 ≝ {A2a, Transport}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, A2aTransport)}
# 功能 ⊢ {A2a_Transport, Init_A2a, Validate_Transport}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---

import logging
import queue
import threading
import uuid
from typing import Any

_log = logging.getLogger(__name__)


class A2ATransport:
    """In-process A2A (Agent-to-Agent) transport layer.

    Provides thread-safe message passing between agents using per-agent inbox
    queues backed by :class:`queue.Queue`. Each agent has its own inbox; callers
    ``send_message`` to put a message into the target's queue and
    ``receive_message`` to pop from a given agent's inbox.

    EventBus events (``a2a.message.sent``, ``a2a.message.received``) are
    emitted best-effort via the shared-lib global EventBus registry so this
    module has no hard dependency on D-Execution.
    """

    def __init__(self) -> None:
        self._queue_lock = threading.Lock()
        self._inboxes: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._counter = 0
        self._counter_lock = threading.Lock()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _inbox(self, agent_id: str) -> queue.Queue[dict[str, Any]]:
        """Return (lazily creating) the inbox queue for *agent_id*."""
        with self._queue_lock:
            if agent_id not in self._inboxes:
                self._inboxes[agent_id] = queue.Queue()
            return self._inboxes[agent_id]

    def _next_msg_id(self) -> str:
        with self._counter_lock:
            self._counter += 1
            return f"a2a_{self._counter:06d}_{uuid.uuid4().hex[:6]}"

    def _emit(self, event_type: str, payload: dict) -> bool:
        try:
            from kairon_lib.events import get_global_event_bus, make_event  # type: ignore[import-not-found]
        except ImportError:
            _log.debug("[A2ATransport] kairon_lib.events unavailable")
            return False

        bus = get_global_event_bus()
        if bus is None:
            _log.debug("[A2ATransport] Global EventBus not yet registered")
            return False

        try:
            bus.publish(make_event(event_type, "a2a_transport", payload))
        except Exception as exc:
            _log.debug("[A2ATransport] Failed to emit %s: %s", event_type, exc)
            return False
        return True

    # ── Public API ────────────────────────────────────────────────────────────

    def send_message(
        self,
        target_agent_id: str,
        message: dict,
        timeout: float = 30.0,  # reserved for future network transport tiers
    ) -> dict:
        """Place *message* into *target_agent_id*'s inbox.

        Returns a delivery receipt containing ``msg_id``, ``status``, and
        ``target``.  The *timeout* parameter is reserved for future network-
        transport tiers and is not used for in-process delivery.
        """
        msg_id = self._next_msg_id()
        envelope: dict[str, Any] = {
            "msg_id": msg_id,
            "target": target_agent_id,
            "payload": message,
        }
        self._inbox(target_agent_id).put(envelope)
        self._emit("a2a.message.sent", {"target": target_agent_id, "msg_id": msg_id})
        _log.debug("[A2ATransport] sent msg_id=%s → agent=%s", msg_id, target_agent_id)
        return {"msg_id": msg_id, "status": "delivered", "target": target_agent_id}

    def receive_message(
        self,
        source_agent_id: str,
        timeout: float = 30.0,
    ) -> dict | None:
        """Pop and return the next message from *source_agent_id*'s inbox.

        Blocks for up to *timeout* seconds.  Returns ``None`` if the inbox
        is empty when the timeout expires.
        """
        try:
            envelope = self._inbox(source_agent_id).get(timeout=timeout)
        except queue.Empty:
            return None

        msg_id = envelope.get("msg_id", "?")
        self._emit(
            "a2a.message.received",
            {"agent_id": source_agent_id, "msg_id": msg_id},
        )
        _log.debug("[A2ATransport] received msg_id=%s for agent=%s", msg_id, source_agent_id)
        return envelope

    def broadcast(
        self,
        message: dict,
        agent_ids: list[str],
    ) -> list[dict]:
        """Send *message* to every agent in *agent_ids*.

        Returns the list of delivery receipts in the same order as
        *agent_ids*.
        """
        return [self.send_message(agent_id, message) for agent_id in agent_ids]
