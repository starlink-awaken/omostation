from __future__ import annotations

import json
import os
import time

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
    """In-process A2A (Agent-to-Agent) transport layer."""

    def __init__(self) -> None:
        self._queue_lock = threading.Lock()
        self._inboxes: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._counter = 0
        self._counter_lock = threading.Lock()

    # ... (existing methods: _inbox, _next_msg_id, _emit, send_message, receive_message, broadcast)
    # Note: keeping the original structure for backward compat.

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
            from kairon_events import get_global_event_bus, make_event
        except ImportError:
            _log.debug("[A2ATransport] kairon_lib.events unavailable")
            return False

        bus = get_global_event_bus()
        if bus is None:
            _log.debug("[A2ATransport] Global EventBus not yet registered")
            return False

        try:
            bus.publish(make_event(event_type, "a2a_transport", payload))
        except Exception as exc:  # defensive fallback
            _log.debug("[A2ATransport] Failed to emit %s: %s", event_type, exc)
            return False
        return True

    def send_message(
        self,
        target_agent_id: str,
        message: dict,
        timeout: float = 30.0,
    ) -> dict:
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
        try:
            envelope = self._inbox(source_agent_id).get(timeout=timeout)
        except queue.Empty:
            return None

        msg_id = envelope.get("msg_id", "?")
        self._emit(
            "a2a.message.received",
            {"agent_id": source_agent_id, "msg_id": msg_id},
        )
        _log.debug(
            "[A2ATransport] received msg_id=%s for agent=%s", msg_id, source_agent_id
        )
        return envelope

    def broadcast(
        self,
        message: dict,
        agent_ids: list[str],
    ) -> list[dict]:
        return [self.send_message(agent_id, message) for agent_id in agent_ids]


class A2ANetworkTransport(A2ATransport):
    """Network-aware A2A transport layer for Swarm Spine (Phase 3).

    Extends A2ATransport to support cross-node message routing.
    If target_agent_id is "node_id/agent_id" and node_id is remote,
    the message is forwarded via HTTP to the remote node's Agora API.
    """

    async def send_message_async(
        self,
        target_agent_id: str,
        message: dict,
        timeout: float = 30.0,
    ) -> dict:
        """Asynchronously send a message, with swarm routing support."""
        if "/" not in target_agent_id:
            # In-process fallback
            return self.send_message(target_agent_id, message, timeout)

        node_id, agent_id = target_agent_id.split("/", 1)
        from agora.mcp.swarm import get_swarm

        swarm = get_swarm()
        if node_id == swarm.node_id:
            # Local node but specified with node_id
            return self.send_message(agent_id, message, timeout)

        # Remote node lookup
        node = swarm._nodes.get(node_id)
        if not node or not node.is_online:
            return {
                "status": "error",
                "error": f"target_node_offline: {node_id}",
                "target": target_agent_id,
            }

        # HTTP Forwarding
        import httpx

        from agora.auth.node_identity import NodeIdentityManager

        # ── Phase 9: Sign the payload ──
        nim = NodeIdentityManager()
        identity = nim.load_or_create()
        private_key = nim.get_private_key_b64()

        payload = {
            "target_agent_id": agent_id,
            "message": message,
            "sender_node_id": swarm.node_id,
            "timestamp": time.time(),
        }

        headers = {
            "X-Swarm-Node-ID": swarm.node_id,
        }

        if private_key:
            # Sign exact bytes to prevent serialization drift
            payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            signature = identity.sign(payload_bytes, private_key)
            headers["X-Swarm-Signature"] = signature
        else:
            payload_bytes = json.dumps(payload).encode("utf-8")

        mcp_port = getattr(
            node, "mcp_port", int(os.environ.get("AGORA_MCP_HTTP_PORT", "7422"))
        )
        url = f"http://{node.host}:{mcp_port}/api/v1/a2a/send"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, content=payload_bytes, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # defensive fallback
            _log.error("[A2ANetworkTransport] forward_failed to %s: %s", url, e)
            return {
                "status": "error",
                "error": f"forward_failed: {e}",
                "target": target_agent_id,
            }
