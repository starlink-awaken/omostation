"""G-DEL.3 — Multi-node state sync (in-process) + latency probe.

Target: sync latency < 100ms (BET-3e602). Measures p50/p95/p99 of put→visible rounds.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeStore:
    node_id: str
    data: dict[str, Any] = field(default_factory=dict)
    version: int = 0


class StateSyncCluster:
    """Eventually-consistent fan-out sync across logical nodes (immediate for probe)."""

    def __init__(self, node_ids: list[str]) -> None:
        if len(node_ids) < 2:
            raise ValueError("need >=2 nodes")
        self.nodes = {n: NodeStore(node_id=n) for n in node_ids}

    def put(self, node_id: str, key: str, value: Any) -> float:
        """Write on node and sync to peers; return latency_ms until all peers see key."""
        if node_id not in self.nodes:
            raise KeyError(node_id)
        t0 = time.perf_counter()
        src = self.nodes[node_id]
        src.data[key] = value
        src.version += 1
        # sync to all peers
        for nid, store in self.nodes.items():
            if nid == node_id:
                continue
            store.data[key] = value
            store.version = max(store.version, src.version)
        # visibility check
        for store in self.nodes.values():
            if store.data.get(key) != value:
                raise RuntimeError("sync visibility failed")
        return (time.perf_counter() - t0) * 1000.0

    def get(self, node_id: str, key: str) -> Any:
        return self.nodes[node_id].data.get(key)


def measure_sync_latency(
    *,
    n_nodes: int = 4,
    n_ops: int = 500,
) -> dict[str, Any]:
    nodes = [f"node-{i}" for i in range(n_nodes)]
    cluster = StateSyncCluster(nodes)
    samples: list[float] = []
    for i in range(n_ops):
        writer = nodes[i % n_nodes]
        lat = cluster.put(writer, f"k-{i}", {"i": i, "t": time.time()})
        samples.append(lat)
    samples.sort()
    def pct(p: float) -> float:
        if not samples:
            return 0.0
        idx = min(len(samples) - 1, max(0, int(round((p / 100.0) * (len(samples) - 1)))))
        return samples[idx]
    p50, p95, p99 = pct(50), pct(95), pct(99)
    from caliber import stamp_physical_goal  # noqa: PLC0415

    return stamp_physical_goal(
        {
            "n_nodes": n_nodes,
            "n_ops": n_ops,
            "p50_ms": round(p50, 4),
            "p95_ms": round(p95, 4),
            "p99_ms": round(p99, 4),
            "max_ms": round(max(samples) if samples else 0.0, 4),
            "gate": "G-DEL.3",
            "kpi": "sync_latency_p99 < 100ms",
            "env": "in-process multi-node sync (not physical multi-host network)",
        },
        sim_ok=p99 < 100.0,
        physical_hosts=0,
    )
