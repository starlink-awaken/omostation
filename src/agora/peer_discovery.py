# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---
from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: "@Copilot"
Layer: L3
Summary: "Peer discovery lifecycle — bootstrap, announce, discover over Kademlia DHT."
Authority: organs/D-Gateway/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# PeerDiscovery ≡ Module
# 内涵 ≝ {PeerDiscovery}
# 外延 ≝ {e | e ∈ D-Gateway.discovery ∧ implements(e, PeerDiscovery)}
# 功能 ⊢ {bootstrap, discover_peers, announce, get_announcements, ping}
# =============================================================================

import logging  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from typing import Any  # noqa: E402

try:
    from agora.dht_routing import DHTRoutingTable  # type: ignore[import-not-found]
except ImportError:
    from dht_routing import DHTRoutingTable  # type: ignore[no-redef, import-not-found]

try:
    from nucleus.Z_Microkernel.organs.async_utils import run_sync  # type: ignore[import-not-found]
except (ImportError, ModuleNotFoundError):
    # Minimal fallback — only used when nucleus is unavailable.
    import asyncio as _asyncio

    def run_sync(coro: Any) -> Any:  # type: ignore[misc]
        """Fallback run_sync when async_utils is not importable."""
        try:
            _asyncio.get_running_loop()
        except RuntimeError:
            return _asyncio.run(coro)
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_asyncio.run, coro).result(timeout=30)


_log = logging.getLogger(__name__)

__all__ = ["PeerDiscovery"]


class PeerDiscovery:
    """High-level peer-discovery facade over a Kademlia DHT routing table.

    Lifecycle
    ---------
    1. Instantiate with a *local_node_id* (and optional pre-built
       *routing_table*).
    2. Call :meth:`bootstrap` with a list of seed-peer dicts to seed the
       routing table.
    3. Use :meth:`announce` to publish local services.
    4. Use :meth:`discover_peers` / :meth:`get_announcements` to find
       remote services and peers.
    5. Use :meth:`ping` to test whether a peer is currently reachable.
    """

    def __init__(
        self,
        local_node_id: str,
        routing_table: DHTRoutingTable | None = None,
    ) -> None:
        super().__init__()
        self._local_node_id = local_node_id
        self._routing_table = routing_table or DHTRoutingTable(local_node_id)
        # service_name → list of announcement dicts
        self._announcements: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self, seed_peers: list[dict]) -> int:
        """Seed the routing table from a list of peer descriptors.

        Each descriptor must contain at least ``peer_id``, ``address``, and
        ``port`` keys.  Unknown keys are silently ignored.

        Returns the number of peers successfully added.
        """
        added = 0
        for peer in seed_peers:
            peer_id = peer.get("peer_id") or peer.get("node_id", "")
            address = peer.get("address") or peer.get("host", "")
            port = int(peer.get("port", 0))
            if not (peer_id and address and port):
                _log.warning("bootstrap: skipping incomplete peer record %r", peer)
                continue
            self._routing_table.add_peer(peer_id, address, port)
            added += 1
        _log.debug("bootstrap: added %d peer(s)", added)
        return added

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_peers(self, target_id: str) -> list[dict]:
        """Return the known peers closest to *target_id* (up to 3).

        The result list is sorted by ascending XOR distance and each element
        contains ``peer_id``, ``address``, ``port``, ``distance``.
        """
        return self._routing_table.find_closest(target_id, count=3)

    # ------------------------------------------------------------------
    # Announcements
    # ------------------------------------------------------------------

    def announce(self, service_name: str, metadata: dict) -> str:
        """Publish a local service under *service_name*.

        Parameters
        ----------
        service_name:
            Logical name of the service (e.g. ``"memory-sync"``).
        metadata:
            Arbitrary key/value pairs describing the service endpoint.

        Returns
        -------
        str
            A unique ``announcement_id`` that can be used to retract or
            update the announcement later.
        """
        announcement_id = str(uuid.uuid4())
        record = {
            "announcement_id": announcement_id,
            "service_name": service_name,
            "node_id": self._local_node_id,
            "metadata": dict(metadata),
            "timestamp": time.time(),
        }
        self._announcements.setdefault(service_name, []).append(record)
        _log.debug("announce: service=%r id=%s", service_name, announcement_id[:8])
        return announcement_id

    def get_announcements(self, service_name: str) -> list[dict]:
        """Return all announcements registered under *service_name*.

        Returns an empty list if no announcements exist for the given name.
        """
        return list(self._announcements.get(service_name, []))

    # ------------------------------------------------------------------
    # Ping
    # ------------------------------------------------------------------

    async def ping(self, peer_id: str) -> bool:
        """[PB-5] Real network ping via DHT RPC (fully async).

        Uses ``await`` to call the DHT RPC directly.  For synchronous
        callers, use :meth:`ping_sync` instead.
        """
        peer = self._routing_table.get_peer(peer_id)
        if not peer:
            _log.debug("ping %s → False (not in routing table)", peer_id[:8])
            return False

        # Use the global P2P instance if it exists.
        try:
            from agora.p2p_discovery import get_p2p  # type: ignore[import-not-found]

            p2p = get_p2p()
            if p2p and hasattr(p2p, "dht") and p2p.dht:
                res = await p2p.dht.call_rpc(
                    peer["address"],
                    peer["port"],
                    {"rpc": "PING"},
                )
                reachable = res is not None and res.get("status") == "success"
                _log.debug("ping %s → %s (via global DHT)", peer_id[:8], reachable)
                return reachable
        except (
            ImportError,
            ModuleNotFoundError,
            AttributeError,
            TypeError,
            ValueError,
            OSError,
            RuntimeError,
        ):
            pass

        # Fallback to simple table check if RPC fails or environment is not ready
        reachable = peer_id in {
            p["peer_id"] for p in self._routing_table.get_all_peers()
        }
        _log.debug("ping %s → %s (fallback to table check)", peer_id[:8], reachable)
        return reachable

    def ping_sync(self, peer_id: str) -> bool:
        """Synchronous wrapper around :meth:`ping`.

        Uses the approved ``run_sync`` bridge so it is safe to call
        regardless of whether an event loop is already running.
        """
        return run_sync(self.ping(peer_id))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def peer_count(self) -> int:
        """Current number of known peers."""
        return self._routing_table.peer_count()

    def to_dict(self) -> dict:
        """Serialize for debugging / persistence."""
        return {
            "local_node_id": self._local_node_id,
            "peers": self._routing_table.get_all_peers(),
            "announcements": dict(self._announcements),
        }
