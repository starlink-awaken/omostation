"""Zero-Config Local Edge Mesh Node Discovery (ADR-0202).

Discovers and tracks compute fabric peer nodes in the local network topology,
monitoring VRAM budgets, thermal pressure, and loaded model instances.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("omlxc.mesh")


@dataclass
class MeshNodeInfo:
    """局域网边缘算力节点信息."""

    node_id: str
    host: str
    port: int = 8765
    platform: str = "apple"  # apple (Apple Silicon), nvidia (CUDA), cpu
    vram_total_gb: float = 32.0
    vram_free_gb: float = 24.0
    thermal_pressure: str = "nominal"  # nominal, fair, serious, critical
    loaded_models: list[str] = field(default_factory=list)
    active_jobs: int = 0
    latency_ms: float = 1.0
    last_heartbeat: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_throttled(self) -> bool:
        return self.thermal_pressure in ("serious", "critical")

    @property
    def vram_utilization_ratio(self) -> float:
        if self.vram_total_gb <= 0:
            return 0.0
        return (self.vram_total_gb - self.vram_free_gb) / self.vram_total_gb

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "endpoint": f"{self.host}:{self.port}",
            "platform": self.platform,
            "vram_free_gb": self.vram_free_gb,
            "vram_total_gb": self.vram_total_gb,
            "vram_utilization": f"{self.vram_utilization_ratio * 100:.1f}%",
            "thermal_pressure": self.thermal_pressure,
            "is_throttled": self.is_throttled,
            "loaded_models": self.loaded_models,
            "active_jobs": self.active_jobs,
            "latency_ms": self.latency_ms,
            "last_heartbeat": self.last_heartbeat,
        }


class MeshDiscoveryEngine:
    """局域网算力网格拓扑发现引擎."""

    def __init__(self, local_node_id: str = "node-local") -> None:
        self.local_node_id = local_node_id
        self._nodes: dict[str, MeshNodeInfo] = {}

    def register_peer(self, node: MeshNodeInfo) -> None:
        """注册或更新局域网对等节点."""
        self._nodes[node.node_id] = node
        logger.debug(f"Registered mesh node {node.node_id} at {node.host}:{node.port}")

    def list_active_nodes(self) -> list[MeshNodeInfo]:
        """列出当前所有在线可用节点."""
        return sorted(self._nodes.values(), key=lambda n: (n.is_throttled, -n.vram_free_gb, n.latency_ms))

    def find_best_placement(self, model_id: str, priority: str = "P1") -> MeshNodeInfo | None:
        """为特定模型和优先级计算最佳放置/漫游节点."""
        active = self.list_active_nodes()
        if not active:
            return None

        # 1. 优先选择已加载该模型的节点
        with_model = [n for n in active if model_id in n.loaded_models and not n.is_throttled]
        if with_model:
            return with_model[0]

        # 2. 其次选择非节流且可用显存最大的节点
        healthy = [n for n in active if not n.is_throttled and n.vram_free_gb >= 4.0]
        if healthy:
            return healthy[0]

        # 3. 兜底返回首个节点
        return active[0]
