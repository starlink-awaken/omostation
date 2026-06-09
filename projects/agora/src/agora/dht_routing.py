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
Summary: "Simplified Kademlia-style DHT routing table — XOR metric, k-bucket peer storage."
Authority: organs/D-Gateway/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# DHTRoutingTable ≡ Module
# 内涵 ≝ {DHTRoutingTable}
# 外延 ≝ {e | e ∈ D-Gateway.discovery ∧ implements(e, DHTRoutingTable)}
# 功能 ⊢ {add_peer, remove_peer, find_closest, get_all_peers, peer_count}
# =============================================================================

import hashlib  # noqa: E402
import logging  # noqa: E402
from dataclasses import dataclass  # noqa: E402

_log = logging.getLogger(__name__)

__all__ = ["DHTRoutingTable", "xor_distance"]

# ---------------------------------------------------------------------------
# XOR distance helper
# ---------------------------------------------------------------------------


def xor_distance(a: str, b: str) -> int:
    """Return XOR distance between two peer/node IDs.

    Each ID is hashed with SHA-1 to produce a 160-bit integer; the XOR of
    those integers is the Kademlia distance.  The function is symmetric and
    ``xor_distance(x, x) == 0`` for any *x*.
    """
    ha = int(hashlib.sha1(a.encode()).hexdigest(), 16)  # noqa: S324
    hb = int(hashlib.sha1(b.encode()).hexdigest(), 16)  # noqa: S324
    return ha ^ hb


# ---------------------------------------------------------------------------
# Internal peer record
# ---------------------------------------------------------------------------


@dataclass
class _PeerEntry:
    peer_id: str
    address: str
    port: int


# ---------------------------------------------------------------------------
# DHTRoutingTable
# ---------------------------------------------------------------------------


class DHTRoutingTable:
    """Simplified Kademlia routing table using a single flat k-bucket.

    Parameters
    ----------
    node_id:
        The local node's identifier string (any non-empty str).
    k:
        Maximum number of peers retained per bucket (default 20).
    """

    def __init__(self, node_id: str, k: int = 20) -> None:
        super().__init__()
        self._node_id = node_id
        self._k = k
        # Simple flat storage: peer_id → _PeerEntry.  Full Kademlia would
        # shard by distance-prefix; one bucket is correct for this scope.
        self._peers: dict[str, _PeerEntry] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_peer(self, peer_id: str, address: str, port: int) -> None:
        """Insert or refresh a peer.

        If the routing table is already at capacity (k peers) and the peer is
        not already known, the peer at maximum XOR distance is evicted first
        to make room (LRU-by-distance eviction, consistent with Kademlia).
        """
        if peer_id == self._node_id:
            return  # Never store ourselves.

        if peer_id in self._peers:
            # Refresh in-place.
            self._peers[peer_id] = _PeerEntry(peer_id, address, port)
            return

        if len(self._peers) >= self._k:
            # Evict the peer furthest from us.
            furthest = max(
                self._peers.keys(),
                key=lambda pid: xor_distance(self._node_id, pid),
            )
            del self._peers[furthest]
            _log.debug("k-bucket full — evicted %s", furthest[:8])

        self._peers[peer_id] = _PeerEntry(peer_id, address, port)

    def get_peer(self, peer_id: str) -> dict | None:
        """Retrieve a specific peer by ID."""
        entry = self._peers.get(peer_id)
        if entry:
            return {
                "peer_id": entry.peer_id,
                "address": entry.address,
                "port": entry.port,
            }
        return None

    def remove_peer(self, peer_id: str) -> bool:
        """Remove a peer by ID.

        Returns ``True`` if the peer was present (and removed), ``False``
        if the peer was not known.
        """
        if peer_id in self._peers:
            del self._peers[peer_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def find_closest(self, target_id: str, count: int = 3) -> list[dict]:
        """Return up to *count* peers sorted by XOR distance to *target_id*.

        Each result dict contains: ``peer_id``, ``address``, ``port``,
        ``distance`` (integer XOR value).
        """
        results = []
        for entry in self._peers.values():
            dist = xor_distance(target_id, entry.peer_id)
            results.append(
                {
                    "peer_id": entry.peer_id,
                    "address": entry.address,
                    "port": entry.port,
                    "distance": dist,
                }
            )
        results.sort(key=lambda r: r["distance"])
        return results[:count]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_all_peers(self) -> list[dict]:
        """Return all known peers as a list of dicts.

        Each dict contains: ``peer_id``, ``address``, ``port``.
        """
        return [
            {"peer_id": e.peer_id, "address": e.address, "port": e.port}
            for e in self._peers.values()
        ]

    def peer_count(self) -> int:
        """Number of peers currently in the routing table."""
        return len(self._peers)
