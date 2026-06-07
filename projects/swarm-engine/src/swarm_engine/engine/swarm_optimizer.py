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
# Swarm Optimizer ≡ Module
# 内涵 ≝ {Swarm, Optimizer}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SwarmOptimizer)}
# 功能 ⊢ {Swarm_Optimizer, Init_Swarm, Validate_Optimizer}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import copy
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class OptimizationAction:
    action_id: str
    action_type: str  # "rebalance", "specialize", "merge", "split", "migrate"
    target_nodes: list[str]
    parameters: dict
    reason: str
    confidence: float
    applied: bool = False
    result: dict | None = None


@dataclass
class SwarmTopology:
    nodes: dict[str, dict]  # node_id → {role, load, capabilities, cluster}
    clusters: dict[str, list[str]]  # cluster_id → [node_ids]
    connections: list[tuple[str, str]]  # edges between nodes
    timestamp: float = field(default_factory=time.time)


class SwarmOptimizer:
    """Auto-optimizes swarm topology based on detected emergence patterns."""

    LOAD_IMBALANCE_THRESHOLD = 0.3
    SPECIALIZATION_MIN_SCORE = 0.8
    MERGE_UTILIZATION_THRESHOLD = 0.3
    SPLIT_UTILIZATION_THRESHOLD = 0.9

    def __init__(self, config: dict | None = None) -> None:
        self._config: dict = config or {}
        self._history: list[OptimizationAction] = []
        self._lock = threading.Lock()
        self._stats: dict[str, int] = {
            "total_optimizations": 0,
            "actions_applied": 0,
            "actions_generated": 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        topology: SwarmTopology,
        patterns: list[dict] | None = None,
    ) -> list[OptimizationAction]:
        actions: list[OptimizationAction] = []

        imbalance = self.detect_imbalance(topology)
        if imbalance is not None:
            actions.append(imbalance)

        actions.extend(self.detect_specialization(topology))
        actions.extend(self.detect_merge_candidates(topology))
        actions.extend(self.detect_split_candidates(topology))

        if patterns:
            for pat in patterns:
                pat_type = pat.get("type", "")
                if pat_type in ("clustering", "load_shift"):
                    source = pat.get("source", "")
                    destination = pat.get("destination", "")
                    if source and destination:
                        action = OptimizationAction(
                            action_id=uuid.uuid4().hex[:8],
                            action_type="migrate",
                            target_nodes=[source, destination],
                            parameters={"pattern": pat},
                            reason=f"Migration triggered by {pat_type} pattern",
                            confidence=float(pat.get("confidence", 0.5)),
                        )
                        actions.append(action)

        with self._lock:
            self._history.extend(actions)
            self._stats["total_optimizations"] += 1
            self._stats["actions_generated"] += len(actions)

        _log.debug(
            "optimize produced %d actions for %d nodes",
            len(actions),
            len(topology.nodes),
        )
        return actions

    def apply_action(
        self,
        topology: SwarmTopology,
        action: OptimizationAction,
    ) -> SwarmTopology:
        new_topo = copy.deepcopy(topology)

        if action.action_type == "rebalance":
            loads = [new_topo.nodes[nid].get("load", 0.0) for nid in action.target_nodes if nid in new_topo.nodes]
            if loads:
                avg = sum(loads) / len(loads)
                for nid in action.target_nodes:
                    if nid in new_topo.nodes:
                        new_topo.nodes[nid]["load"] = avg

        elif action.action_type == "specialize":
            role = action.parameters.get("role", "specialist")
            if action.target_nodes and action.target_nodes[0] in new_topo.nodes:
                new_topo.nodes[action.target_nodes[0]]["role"] = role

        elif action.action_type == "merge":
            if len(action.target_nodes) >= 2:
                dst_cluster = action.target_nodes[0]
                src_cluster = action.target_nodes[1]
                src_members = new_topo.clusters.pop(src_cluster, [])
                if dst_cluster not in new_topo.clusters:
                    new_topo.clusters[dst_cluster] = []
                new_topo.clusters[dst_cluster].extend(src_members)
                for nid in src_members:
                    if nid in new_topo.nodes:
                        new_topo.nodes[nid]["cluster"] = dst_cluster

        elif action.action_type == "split":
            if action.target_nodes:
                cluster_id = action.target_nodes[0]
                new_cluster_id = action.parameters.get("new_cluster_id", f"{cluster_id}_split")
                members = new_topo.clusters.get(cluster_id, [])
                if len(members) >= 2:
                    mid = len(members) // 2
                    stay = members[:mid]
                    move = members[mid:]
                    new_topo.clusters[cluster_id] = stay
                    new_topo.clusters[new_cluster_id] = move
                    for nid in move:
                        if nid in new_topo.nodes:
                            new_topo.nodes[nid]["cluster"] = new_cluster_id

        elif action.action_type == "migrate":
            if len(action.target_nodes) >= 2:
                src_node = action.target_nodes[0]
                dst_node = action.target_nodes[1]
                if src_node in new_topo.nodes:
                    new_topo.nodes[src_node]["load"] = max(0.0, new_topo.nodes[src_node].get("load", 0.0) - 0.1)
                if dst_node in new_topo.nodes:
                    new_topo.nodes[dst_node]["load"] = new_topo.nodes[dst_node].get("load", 0.0) + 0.1

        action.applied = True
        action.result = {"success": True}

        with self._lock:
            self._stats["actions_applied"] += 1

        _log.debug("applied action %s (%s)", action.action_id, action.action_type)
        return new_topo

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def detect_imbalance(self, topology: SwarmTopology) -> OptimizationAction | None:
        loads = [n.get("load", 0.0) for n in topology.nodes.values()]
        if len(loads) < 2:
            return None

        mean = sum(loads) / len(loads)
        variance = sum((v - mean) ** 2 for v in loads) / len(loads)
        std_dev = variance**0.5
        ratio = std_dev / max(mean, 0.01)

        if ratio > self.LOAD_IMBALANCE_THRESHOLD:
            return OptimizationAction(
                action_id=uuid.uuid4().hex[:8],
                action_type="rebalance",
                target_nodes=list(topology.nodes.keys()),
                parameters={"mean_load": mean, "std_dev": std_dev},
                reason=f"Load imbalance detected (ratio={ratio:.2f})",
                confidence=min(1.0, ratio),
            )
        return None

    def detect_specialization(self, topology: SwarmTopology) -> list[OptimizationAction]:
        actions: list[OptimizationAction] = []
        for nid, info in topology.nodes.items():
            caps: dict[str, float] = info.get("capabilities", {})
            if not caps:
                continue
            role = info.get("role", "general")
            if role and role != "general":
                continue

            best_cap = max(caps, key=caps.get)  # type: ignore[arg-type]
            best_score = caps[best_cap]
            if best_score >= self.SPECIALIZATION_MIN_SCORE:
                actions.append(
                    OptimizationAction(
                        action_id=uuid.uuid4().hex[:8],
                        action_type="specialize",
                        target_nodes=[nid],
                        parameters={"role": best_cap, "score": best_score},
                        reason=(f"Node {nid} excels at {best_cap} (score={best_score:.2f})"),
                        confidence=best_score,
                    )
                )
        return actions

    def detect_merge_candidates(self, topology: SwarmTopology) -> list[OptimizationAction]:
        low_util: list[str] = []
        for cid, members in topology.clusters.items():
            if not members:
                continue
            avg_load = sum(topology.nodes.get(nid, {}).get("load", 0.0) for nid in members) / len(members)
            if avg_load < self.MERGE_UTILIZATION_THRESHOLD:
                low_util.append(cid)

        actions: list[OptimizationAction] = []
        for i in range(0, len(low_util) - 1, 2):
            actions.append(
                OptimizationAction(
                    action_id=uuid.uuid4().hex[:8],
                    action_type="merge",
                    target_nodes=[low_util[i], low_util[i + 1]],
                    parameters={},
                    reason=(f"Clusters {low_util[i]} and {low_util[i + 1]} are under-utilized"),
                    confidence=0.7,
                )
            )
        return actions

    def detect_split_candidates(self, topology: SwarmTopology) -> list[OptimizationAction]:
        actions: list[OptimizationAction] = []
        for cid, members in topology.clusters.items():
            if len(members) < 2:
                continue
            avg_load = sum(topology.nodes.get(nid, {}).get("load", 0.0) for nid in members) / len(members)
            if avg_load > self.SPLIT_UTILIZATION_THRESHOLD:
                actions.append(
                    OptimizationAction(
                        action_id=uuid.uuid4().hex[:8],
                        action_type="split",
                        target_nodes=[cid],
                        parameters={"new_cluster_id": f"{cid}_split"},
                        reason=(f"Cluster {cid} is overloaded (avg_load={avg_load:.2f})"),
                        confidence=min(1.0, avg_load),
                    )
                )
        return actions

    # ------------------------------------------------------------------
    # Evaluation & accessors
    # ------------------------------------------------------------------

    def evaluate_topology(self, topology: SwarmTopology) -> dict:
        loads = [n.get("load", 0.0) for n in topology.nodes.values()]
        n = len(loads)
        mean = sum(loads) / n if n else 0.0
        variance = (sum((v - mean) ** 2 for v in loads) / n) if n else 0.0
        std_dev = variance**0.5

        ratio = std_dev / max(mean, 0.01) if n else 0.0
        balance_score = max(0.0, min(1.0, 1.0 - ratio))

        num_nodes = len(topology.nodes)
        max_edges = num_nodes * (num_nodes - 1) / 2
        connectivity = len(topology.connections) / max(max_edges, 1)
        connectivity = max(0.0, min(1.0, connectivity))

        return {
            "balance_score": balance_score,
            "utilization": mean,
            "connectivity": connectivity,
            "node_count": num_nodes,
            "cluster_count": len(topology.clusters),
        }

    def get_history(self) -> list[OptimizationAction]:
        with self._lock:
            return list(self._history)

    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._stats)
