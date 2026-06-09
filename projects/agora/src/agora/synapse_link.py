from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: "@Copilot"
Layer: L3
Summary: "SynapseLink — B-OS node-to-node handshake, heartbeat, and peer registry."
Authority: organs/D-Gateway/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Synapse Link ≡ Protocol
# 内涵 ≝ {SynapseLink, RemoteNode, NodeStatus}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, SynapseLink)}
# 功能 ⊢ {Handshake, Heartbeat, Peer_Registry}
# =============================================================================
import asyncio  # noqa: E402
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from enum import StrEnum  # noqa: E402

from agora.auth.node_identity import NodeIdentity  # type: ignore[import-not-found]  # noqa: E402

_log = logging.getLogger(__name__)

__all__ = ["NodeStatus", "RemoteNode", "SynapseLink"]

# ---------------------------------------------------------------------------
# HMAC-SHA256 authentication helpers (TD-008)
# ---------------------------------------------------------------------------

_SOVEREIGN_KEY_ENV = "SHAREDBRAIN_SOVEREIGN_KEY"
_SIGNATURE_WINDOW_S = 30  # seconds; reject messages older than this


def _compute_handshake_signature(
    node_id: str, timestamp: float, sovereign_key: str
) -> str:
    """Compute HMAC-SHA256 signature for a handshake message.

    The signed message is ``"{node_id}:{timestamp:.3f}"``.
    """
    msg = f"{node_id}:{timestamp:.3f}".encode()
    key = sovereign_key.encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _verify_handshake_signature(
    node_id: str,
    timestamp: float,
    signature: str,
    sovereign_key: str,
) -> bool:
    """Verify handshake HMAC-SHA256 signature.

    Returns ``False`` if the signature is invalid **or** the timestamp is
    more than ``_SIGNATURE_WINDOW_S`` seconds old (replay protection).
    """
    if abs(time.time() - timestamp) > _SIGNATURE_WINDOW_S:
        return False
    expected = _compute_handshake_signature(node_id, timestamp, sovereign_key)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Node status enum
# ---------------------------------------------------------------------------


class NodeStatus(StrEnum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Remote node record
# ---------------------------------------------------------------------------


@dataclass
class RemoteNode:
    """Represents a remote B-OS peer with connection metadata."""

    node_id: str
    host: str
    port: int
    public_key: str
    display_name: str = ""
    status: NodeStatus = NodeStatus.UNKNOWN
    last_seen: datetime | None = None
    last_heartbeat_ms: float = 0.0
    # Internal failure counter — reset on success.
    _failure_count: int = field(default=0, repr=False, compare=False)

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"


# ---------------------------------------------------------------------------
# SynapseLink
# ---------------------------------------------------------------------------


class SynapseLink:
    """Manages connections to remote B-OS nodes.

    Responsibilities:
    - Peer registry (add / remove / list)
    - Synapse Link handshake (/synapse/hello)
    - Periodic heartbeat loop (/synapse/ping), marking nodes OFFLINE after
      ``offline_threshold`` consecutive failures.
    - Incoming /synapse/hello handling (returns our identity).
    """

    def __init__(
        self,
        local_identity: NodeIdentity,
        *,
        heartbeat_interval: int = 30,
        handshake_timeout: float = 5.0,
        offline_threshold: int = 3,
    ) -> None:
        self._identity = local_identity
        self._heartbeat_interval = heartbeat_interval
        self._handshake_timeout = handshake_timeout
        self._offline_threshold = offline_threshold
        self._nodes: dict[str, RemoteNode] = {}
        self._heartbeat_task: asyncio.Task | None = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Peer registry
    # ------------------------------------------------------------------

    def add_node(self, node: RemoteNode) -> None:
        """Register a remote node (upsert by node_id)."""
        self._nodes[node.node_id] = node
        _log.debug(
            "SynapseLink: added node %s (%s:%d)", node.node_id, node.host, node.port
        )

    def remove_node(self, node_id: str) -> None:
        """Deregister a remote node by node_id (no-op if unknown)."""
        self._nodes.pop(node_id, None)

    def get_node(self, node_id: str) -> RemoteNode | None:
        return self._nodes.get(node_id)

    def list_nodes(self) -> list[RemoteNode]:
        return list(self._nodes.values())

    def list_online(self) -> list[RemoteNode]:
        """Return only nodes whose status is ONLINE."""
        return [n for n in self._nodes.values() if n.status == NodeStatus.ONLINE]

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    async def handshake(self, node: RemoteNode) -> bool:
        """Perform the Synapse Link handshake with *node*.

        Protocol:
          1. POST {node.endpoint}/synapse/hello
             Body: {node_id, public_key, display_name}
          2. Parse remote identity from response.
          3. Update *node* fields from response; mark ONLINE on success.

        Returns True if handshake succeeded.
        """
        payload = {
            "node_id": self._identity.node_id,
            "public_key": self._identity.public_key,
            "display_name": self._identity.display_name,
        }
        # TD-008: include HMAC signature when SOVEREIGN_KEY is configured
        sovereign_key = os.environ.get(_SOVEREIGN_KEY_ENV, "")
        if sovereign_key:
            ts = time.time()
            payload["timestamp"] = ts
            payload["signature"] = _compute_handshake_signature(
                self._identity.node_id, ts, sovereign_key
            )
        url = f"{node.endpoint}/synapse/hello"
        try:
            t0 = time.monotonic()
            response = await self._http_post(
                url, payload, timeout=self._handshake_timeout
            )
            elapsed_ms = (time.monotonic() - t0) * 1000

            # Update remote node metadata from response
            if "node_id" in response:
                node.node_id = response["node_id"]
            node.public_key = response.get("public_key", node.public_key)
            node.display_name = response.get("display_name", node.display_name)
            node.status = NodeStatus.ONLINE
            node.last_seen = datetime.now(UTC)
            node.last_heartbeat_ms = elapsed_ms
            node._failure_count = 0

            # Re-index under (possibly updated) node_id
            self._nodes[node.node_id] = node
            _log.info(
                "SynapseLink: handshake OK with %s (%s) in %.1f ms",
                node.node_id,
                node.host,
                elapsed_ms,
            )
            return True
        except (TimeoutError, OSError, ConnectionError, RuntimeError) as exc:
            _log.warning(
                "SynapseLink: handshake FAILED with %s:%d — %s",
                node.host,
                node.port,
                exc,
            )
            node.status = NodeStatus.OFFLINE
            return False

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def heartbeat(self, node: RemoteNode) -> bool:
        """Send a /synapse/ping heartbeat to *node*.

        - On success: mark ONLINE, reset failure counter, update last_seen.
        - On failure: increment failure counter; mark OFFLINE after
          ``offline_threshold`` consecutive failures.

        Returns True if ping succeeded.
        """
        payload = {"node_id": self._identity.node_id}
        url = f"{node.endpoint}/synapse/ping"
        try:
            t0 = time.monotonic()
            await self._http_post(url, payload, timeout=self._handshake_timeout)
            elapsed_ms = (time.monotonic() - t0) * 1000

            node.status = NodeStatus.ONLINE
            node.last_seen = datetime.now(UTC)
            node.last_heartbeat_ms = elapsed_ms
            node._failure_count = 0
            return True
        except (TimeoutError, OSError, ConnectionError, RuntimeError) as exc:
            node._failure_count += 1
            _log.debug(
                "SynapseLink: heartbeat fail #%d for %s — %s",
                node._failure_count,
                node.node_id,
                exc,
            )
            if node._failure_count >= self._offline_threshold:
                node.status = NodeStatus.OFFLINE
                _log.warning(
                    "SynapseLink: node %s marked OFFLINE after %d failures",
                    node.node_id,
                    node._failure_count,
                )
            else:
                node.status = NodeStatus.DEGRADED
            return False

    async def start_heartbeat_loop(self) -> None:  # pragma: no cover
        """Background coroutine: ping all known nodes every heartbeat_interval seconds.

        Designed to be started via ``asyncio.create_task(link.start_heartbeat_loop())``.
        Runs until cancelled.
        """
        _log.info(
            "SynapseLink: heartbeat loop started (interval=%ds)",
            self._heartbeat_interval,
        )
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            for node in list(self._nodes.values()):
                try:
                    await self.heartbeat(node)
                except (OSError, ValueError) as exc:
                    _log.error(
                        "SynapseLink: unexpected heartbeat error for %s: %s",
                        node.node_id,
                        exc,
                    )

    # ------------------------------------------------------------------
    # Incoming hello handler
    # ------------------------------------------------------------------

    def handle_hello(self, payload: dict) -> dict:
        """Handle an incoming /synapse/hello request.

        Registers the caller as a RemoteNode (or updates an existing entry)
        and returns our own identity for the mutual exchange.

        Args:
            payload: dict with at minimum ``node_id`` and ``public_key``.

        Returns:
            dict with our ``node_id``, ``public_key``, and ``display_name``.
        """
        remote_id = payload.get("node_id", "")
        # TD-008: verify HMAC signature when SOVEREIGN_KEY is configured (opt-in)
        sovereign_key = os.environ.get(_SOVEREIGN_KEY_ENV, "")
        if sovereign_key:
            sig = payload.get("signature", "")
            ts = float(payload.get("timestamp", 0.0))
            if not _verify_handshake_signature(remote_id, ts, sig, sovereign_key):
                _log.warning(
                    "SynapseLink: rejected hello from %s — invalid or expired signature",
                    remote_id,
                )
                return {
                    "error": "invalid_signature",
                    "node_id": self._identity.node_id,
                }
        if remote_id and remote_id not in self._nodes:
            # Auto-register the caller — host/port unknown at this layer,
            # populated by higher-level HTTP handler if desired.
            node = RemoteNode(
                node_id=remote_id,
                host="",
                port=0,
                public_key=payload.get("public_key", ""),
                display_name=payload.get("display_name", ""),
                status=NodeStatus.ONLINE,
                last_seen=datetime.now(UTC),
            )
            self._nodes[remote_id] = node
            _log.info("SynapseLink: auto-registered incoming hello from %s", remote_id)
        elif remote_id in self._nodes:
            existing = self._nodes[remote_id]
            existing.status = NodeStatus.ONLINE
            existing.last_seen = datetime.now(UTC)

        return {
            "node_id": self._identity.node_id,
            "public_key": self._identity.public_key,
            "display_name": self._identity.display_name,
        }

    # ------------------------------------------------------------------
    # Internal HTTP
    # ------------------------------------------------------------------

    async def _http_post(
        self, url: str, payload: dict, *, timeout: float = 5.0
    ) -> dict:
        """Async HTTP POST — tries httpx, falls back to urllib in an executor."""
        try:
            import httpx  # type: ignore[import]

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except ImportError:
            pass

        # urllib fallback — run in executor to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._urllib_post_sync, url, payload, timeout
        )

    @staticmethod
    def _urllib_post_sync(
        url: str, payload: dict, timeout: float
    ) -> dict:  # pragma: no cover
        data = json.dumps(payload).encode()
        req = urllib.request.Request(  # noqa: S310
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {body[:200]}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError(f"HTTP POST {url} failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoint helpers for MCP server integration
# ---------------------------------------------------------------------------


def synapse_hello_handler(synapse_link: SynapseLink, payload: dict) -> dict:
    """Top-level dispatcher for POST /synapse/hello.

    Suitable for registration in mcp_server.py or any lightweight HTTP router.
    """
    return synapse_link.handle_hello(payload)


def synapse_ping_handler(synapse_link: SynapseLink, payload: dict) -> dict:
    """Top-level dispatcher for POST /synapse/ping.

    Acknowledges the heartbeat from a remote node.
    """
    remote_id = payload.get("node_id", "unknown")
    node = synapse_link.get_node(remote_id)
    if node is not None:
        node.last_seen = datetime.now(UTC)
        node.status = NodeStatus.ONLINE
    return {"status": "pong", "node_id": synapse_link._identity.node_id}
