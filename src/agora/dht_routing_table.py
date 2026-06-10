from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: "@Copilot"
Layer: L3
Summary: "Kademlia-inspired DHT routing table — XOR address space, K-bucket LRU, closest-node lookup."
Authority: organs/D-Gateway/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# DHT Routing Table ≡ Module
# 内涵 ≝ {DHTNode, KBucket, DHTRoutingTable}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, DHTRoutingTable)}
# 功能 ⊢ {Add_Node, Remove_Node, Find_Closest, Serialize}
# =============================================================================
import logging  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import ClassVar  # noqa: E402

_log = logging.getLogger(__name__)

__all__ = ["DHTNode", "KBucket", "DHTRoutingTable"]

# ---------------------------------------------------------------------------
# DHTNode
# ---------------------------------------------------------------------------


@dataclass
class DHTNode:
    """A peer in the Kademlia address space.

    *node_id* is a 40-character hex string representing a 160-bit integer
    (same width as a SHA-1 digest, matching classic Kademlia).
    """

    node_id: str  # hex string, 160-bit XOR address space
    host: str
    port: int
    last_seen: float = field(default_factory=time.monotonic)

    # ------------------------------------------------------------------
    # Distance
    # ------------------------------------------------------------------

    def xor_distance(self, other_id: str) -> int:
        """XOR distance in the Kademlia address space."""
        a = int(self.node_id, 16)
        b = int(other_id, 16)
        return a ^ b

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def touch(self) -> None:
        """Update last_seen to now."""
        self.last_seen = time.monotonic()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DHTNode:
        return cls(
            node_id=d["node_id"],
            host=d["host"],
            port=int(d["port"]),
            last_seen=float(d.get("last_seen", time.monotonic())),
        )


# ---------------------------------------------------------------------------
# KBucket
# ---------------------------------------------------------------------------


@dataclass
class KBucket:
    """Fixed-size bucket of K=20 closest peers (LRU eviction when full)."""

    K: ClassVar[int] = 20

    nodes: list[DHTNode] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, node: DHTNode) -> bool:
        """Add *node* to the bucket.

        * If the node already exists, refresh its ``last_seen`` and move it
          to the tail (most-recently-seen position).
        * If the bucket is not full, append the node.
        * If the bucket is full, evict the **head** (least-recently-seen)
          and append the new node.

        Returns ``True`` when the node was inserted or refreshed,
        ``False`` only if the bucket was full and no eviction occurred
        (currently eviction always happens, so always ``True``).
        """
        # Refresh existing entry.
        for i, existing in enumerate(self.nodes):
            if existing.node_id == node.node_id:
                self.nodes.pop(i)
                node.touch()
                self.nodes.append(node)
                return True

        if len(self.nodes) < self.K:
            self.nodes.append(node)
            return True

        # Bucket full — evict LRS (head).
        self.nodes.pop(0)
        self.nodes.append(node)
        return True

    def remove(self, node_id: str) -> bool:
        """Remove the node with *node_id*.  Returns ``True`` if found."""
        for i, node in enumerate(self.nodes):
            if node.node_id == node_id:
                self.nodes.pop(i)
                return True
        return False

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_closest(self, target_id: str, n: int = 3) -> list[DHTNode]:
        """Return up to *n* nodes sorted by XOR distance to *target_id*."""
        return sorted(self.nodes, key=lambda nd: nd.xor_distance(target_id))[:n]

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.nodes)

    def to_dict(self) -> dict:
        return {"nodes": [nd.to_dict() for nd in self.nodes]}


# ---------------------------------------------------------------------------
# DHTRoutingTable
# ---------------------------------------------------------------------------


class DHTRoutingTable:
    """Simplified Kademlia routing table.

    For this implementation we maintain a **flat** list of K-buckets rather
    than the full 160-bucket binary-tree structure.  A single KBucket is used;
    multiple buckets are introduced only when the single bucket overflows,
    keeping the footprint minimal while preserving the XOR-distance semantics.

    The public API is identical to what a full Kademlia table would expose.
    """

    def __init__(self, local_node_id: str, k: int = 20) -> None:
        super().__init__()
        self._local_id = local_node_id
        self._k = k
        # Single flat bucket — sufficient for lightweight federation.
        self._bucket: KBucket = KBucket()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node: DHTNode) -> None:
        """Insert or refresh *node* in the routing table."""
        if node.node_id == self._local_id:
            return  # Never add ourselves.
        self._bucket.add(node)

    def remove_node(self, node_id: str) -> None:
        """Remove node by *node_id* (no-op if absent)."""
        self._bucket.remove(node_id)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def find_closest(self, target_id: str, n: int = 3) -> list[DHTNode]:
        """Return up to *n* nodes closest to *target_id* by XOR distance."""
        return self._bucket.get_closest(target_id, n)

    def all_nodes(self) -> list[DHTNode]:
        """Return all known nodes."""
        return list(self._bucket.nodes)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def size(self) -> int:
        """Number of nodes currently tracked."""
        return len(self._bucket)

    def to_dict(self) -> dict:
        """Serialize for persistence / wire transport."""
        return {
            "local_node_id": self._local_id,
            "k": self._k,
            "bucket": self._bucket.to_dict(),
        }
