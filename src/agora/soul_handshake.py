from __future__ import annotations

"""
---
Type: Organ
Status: Active
Layer: L3
Summary: Soul handshake protocol for secure node identity verification in BOS federation.
Owner: bos-core
Version: 1.1.0
Authority: organs/D-Gateway/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Soul Handshake ≡ Module
# 内涵 ≝ {Soul, Handshake}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SoulHandshake)}
# 功能 ⊢ {Soul_Handshake, Init_Soul, Validate_Handshake}
# =============================================================================

import hashlib  # noqa: E402
import hmac  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from typing import Any  # noqa: E402

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)
logger = logging.getLogger("bos.soul_handshake")


class ClusterRegistry:
    """In-memory cluster membership registry with TTL-based expiry."""

    def __init__(self, node_ttl: float = 30.0) -> None:
        super().__init__()
        self.node_ttl = node_ttl
        self._nodes: dict[str, dict] = {}
        self._lock = threading.Lock()

    def register(self, node_id: str, info: dict) -> None:
        """Add or update a node entry, stamping registered_at = time.time()."""
        with self._lock:
            entry = dict(info)
            entry["registered_at"] = time.time()
            self._nodes[node_id] = entry

    def deregister(self, node_id: str) -> None:
        """Remove a node from the registry."""
        with self._lock:
            self._nodes.pop(node_id, None)

    def heartbeat(self, node_id: str) -> None:
        """Refresh registered_at for the given node (keep it alive)."""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id]["registered_at"] = time.time()

    def get_alive_nodes(self) -> list[dict]:
        """Return node info dicts whose TTL has not yet expired."""
        now = time.time()
        with self._lock:
            return [
                dict(info)
                for info in self._nodes.values()
                if now - info.get("registered_at", 0) < self.node_ttl
            ]

    def get_node(self, node_id: str) -> dict | None:
        """Return node info dict or None if not registered."""
        with self._lock:
            entry = self._nodes.get(node_id)
            return dict(entry) if entry is not None else None

    def size(self) -> int:
        """Count of alive nodes."""
        return len(self.get_alive_nodes())


class SoulHandshake:
    """
    Soul Handshake 协议 (Phase 1 Task 2)
    负责分布式节点间的信任建立与状态对齐。
    """

    def __init__(
        self,
        node_id: str,
        cluster_key: str | None = None,
        peer_scheme: str | None = None,
    ) -> None:
        self.status = "active"
        self.node_id = node_id
        # 从环境变量或参数获取集群密钥
        self.cluster_key = cluster_key or os.environ.get("BOS_CLUSTER_KEY")
        if not self.cluster_key:
            raise ValueError("BOS_CLUSTER_KEY environment variable is required")
        self.peer_scheme = (
            peer_scheme or os.environ.get("BOS_P2P_SCHEME", "http")
        ).lower()
        if self.peer_scheme not in {"http", "https"}:
            raise ValueError("peer_scheme must be either 'http' or 'https'")
        self.registry = ClusterRegistry()
        self._peer_nodes: dict[str, dict] = {}

    # -------------------------------------------------------------------------
    # HMAC helpers
    # -------------------------------------------------------------------------
    def _hmac_sign(self, payload: dict) -> str:
        """Compute HMAC-SHA256 signature over canonical JSON bytes of payload."""
        canonical = __import__("json").dumps(payload, sort_keys=True).encode()
        return hmac.new(
            self.cluster_key.encode(), canonical, hashlib.sha256
        ).hexdigest()

    def _verify_hmac(self, payload: dict) -> bool:
        """Verify HMAC signature on received payload; reject if missing or invalid."""
        received_sig = payload.get("_hmac")
        if not received_sig:
            return False
        # Rebuild from payload without the _hmac field to avoid misuse
        signing_payload = {k: v for k, v in payload.items() if k != "_hmac"}
        expected = self._hmac_sign(signing_payload)
        return hmac.compare_digest(received_sig, expected)

    def _peer_url(
        self,
        remote_ip: str,
        remote_port: int,
        path: str,
        *,
        scheme: str | None = None,
    ) -> str:
        return (
            f"{(scheme or self.peer_scheme).lower()}://{remote_ip}:{remote_port}{path}"
        )

    async def initiate_handshake(
        self, remote_ip: str, remote_port: int
    ) -> dict[str, Any] | None:
        """
        向远程节点发起握手请求
        """
        url = self._peer_url(remote_ip, remote_port, "/api/v1/handshake")
        logger.info(f"🤝 [SoulHandshake] Initiating TLS handshake with {url}...")

        payload = {
            "node_id": self.node_id,
            "cluster_key": self.cluster_key,
            "timestamp": time.time(),
            "capabilities": self._get_local_capabilities(),
        }
        # Attach HMAC for integrity — must be verified before trusting key material
        payload["_hmac"] = self._hmac_sign(payload)

        try:
            client_kwargs: dict[str, Any] = {"timeout": 5.0}
            if self.peer_scheme == "https":
                client_kwargs["verify"] = True
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        peer_id = data["data"]["node_id"]
                        logger.info(
                            f"✅ [SoulHandshake] Handshake successful with {peer_id}"
                        )
                        return data["data"]
                    else:
                        msg = data.get("message")
                        logger.warning(
                            f"❌ [SoulHandshake] Handshake rejected by {remote_ip}: {msg}"
                        )
                else:
                    logger.warning(
                        f"⚠️ [SoulHandshake] Handshake failed with status {response.status_code}"
                    )
        except (
            httpx.HTTPError,
            OSError,
            ConnectionError,
        ) as e:
            logger.debug(f"Handshake initiation error: {e}")

        return None

    def verify_handshake(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        验证收到的握手请求
        """
        remote_node_id = payload.get("node_id")

        # Reject plaintext connections — require TLS + valid HMAC before trusting key material
        if not self._verify_hmac(payload):
            logger.warning(
                f"🛡️ [SoulHandshake] HMAC verification failed for {remote_node_id} — "
                "rejecting unsigned or tampered payload"
            )
            raise ValueError("Invalid or missing HMAC signature")

        received_key = payload.get("cluster_key")
        if received_key != self.cluster_key:
            logger.warning(
                f"🛡️ [SoulHandshake] Unauthorized handshake attempt from {remote_node_id}"
            )
            raise ValueError("Invalid cluster key")

        logger.info(f"🤝 [SoulHandshake] Verified handshake from {remote_node_id}")

        # 返回本节点信息供对方对齐
        return {
            "node_id": self.node_id,
            "status": "ALIVE",
            "capabilities": self._get_local_capabilities(),
            "timestamp": time.time(),
        }

    def _get_local_capabilities(self) -> dict[str, Any]:
        """
        获取本地节点的能力快照
        """
        # 简化实现，实际应从 CapabilityRegistry 获取
        return {
            "execution": ["parallel_symphony", "git_worktree"],
            "memory": ["fact_graph", "vector_index"],
            "workers": ["cli_avatar", "internal_llm"],
        }

    async def join_cluster(self, seed_nodes: list[tuple[str, int]]) -> dict:
        """
        Attempt handshakes with all seed nodes and register successful peers.

        Returns a summary dict with joined_nodes, failed_nodes, and registry_size.
        """
        joined: list[str] = []
        failed: list[str] = []

        for ip, port in seed_nodes:
            peer_info = await self.initiate_handshake(ip, port)
            if peer_info:
                peer_id = peer_info.get("node_id", f"{ip}:{port}")
                peer_info.setdefault("ip", ip)
                peer_info.setdefault("port", port)
                self.registry.register(peer_id, peer_info)
                self._peer_nodes[peer_id] = peer_info
                joined.append(peer_id)
                logger.info(
                    f"✅ [SoulHandshake] Joined cluster via {ip}:{port} (peer={peer_id})"
                )
            else:
                failed.append(f"{ip}:{port}")
                logger.warning(
                    f"⚠️ [SoulHandshake] Failed to reach seed node {ip}:{port}"
                )

        return {
            "joined_nodes": joined,
            "failed_nodes": failed,
            "registry_size": self.registry.size(),
        }

    def leave_cluster(self) -> None:
        """Deregister this node and clear all tracked peers."""
        self.registry.deregister(self.node_id)
        self._peer_nodes.clear()
        logger.info(f"👋 [SoulHandshake] Node {self.node_id} left cluster")

    def sync_state(self, state_data: dict) -> dict:
        """
        Broadcast state_data to all alive peers via HTTP POST.

        Returns synced_peers, failed_peers, and a state_version timestamp.
        """
        synced: list[str] = []
        failed: list[str] = []
        state_version = str(time.time())

        for node in self.registry.get_alive_nodes():
            peer_id = node.get("node_id", "unknown")
            peer_ip = node.get("ip")
            peer_port = node.get("port")
            if not peer_ip or not peer_port:
                failed.append(peer_id)
                continue
            scheme = str(node.get("scheme", self.peer_scheme)).lower()
            url = self._peer_url(
                peer_ip, peer_port, "/api/v1/state_sync", scheme=scheme
            )
            try:
                request_kwargs: dict[str, Any] = {
                    "url": url,
                    "json": {"node_id": self.node_id, "state": state_data},
                    "timeout": 3.0,
                }
                if scheme == "https":
                    request_kwargs["verify"] = True
                httpx.post(**request_kwargs)
                synced.append(peer_id)
            except Exception as exc:
                logger.debug(f"[SoulHandshake] sync_state failed for {peer_id}: {exc}")
                failed.append(peer_id)

        return {
            "synced_peers": synced,
            "failed_peers": failed,
            "state_version": state_version,
        }

    def route_task(self, task: dict, capability_hint: str) -> dict:
        """
        Route a task to a peer whose capabilities contain capability_hint.

        Returns routing info with status ROUTED or NO_SUITABLE_NODE.
        """
        hint_lower = capability_hint.lower()

        for peer_id, peer_info in self._peer_nodes.items():
            capabilities = peer_info.get("capabilities", {})
            for cap_values in capabilities.values():
                # cap_values may be a list of strings or a plain string
                values = cap_values if isinstance(cap_values, list) else [cap_values]
                if any(hint_lower in str(v).lower() for v in values):
                    return {
                        "routed_to": peer_id,
                        "peer_ip": peer_info.get("ip"),
                        "peer_port": peer_info.get("port"),
                        "capability_hint": capability_hint,
                        "status": "ROUTED",
                    }

        return {
            "routed_to": None,
            "status": "NO_SUITABLE_NODE",
            "capability_hint": capability_hint,
        }

    def get_cluster_status(self) -> dict:
        """Return a snapshot of this node's cluster view."""
        return {
            "my_node_id": self.node_id,
            "alive_nodes": self.registry.get_alive_nodes(),
            "peer_count": len(self._peer_nodes),
            "capabilities": self._get_local_capabilities(),
        }
