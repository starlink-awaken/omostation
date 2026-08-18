"""Dynamic Spillover Roaming Compute Router (ADR-0202).

Routes inference and batch distillation jobs across the local mesh based on QoS,
thermal throttling pressure, and VRAM availability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from omlxc.mesh.node_discovery import MeshDiscoveryEngine, MeshNodeInfo

logger = logging.getLogger("omlxc.mesh.router")


@dataclass
class RoamingDecision:
    """漫游调度决策结果."""

    job_id: str
    model_id: str
    priority: str
    target_node_id: str
    target_endpoint: str
    is_roamed: bool  # True if roamed to remote peer, False if local
    decision_reason: str
    vram_budget_gb: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "model_id": self.model_id,
            "priority": self.priority,
            "target_node_id": self.target_node_id,
            "target_endpoint": self.target_endpoint,
            "is_roamed": self.is_roamed,
            "decision_reason": self.decision_reason,
            "vram_budget_gb": self.vram_budget_gb,
        }


class RoamingComputeRouter:
    """算力任务动态漫游路由器."""

    def __init__(self, discovery_engine: MeshDiscoveryEngine, local_node_id: str = "node-local") -> None:
        self.discovery = discovery_engine
        self.local_node_id = local_node_id

    def route_job(
        self,
        job_id: str,
        model_id: str,
        priority: str = "P1",
        estimated_vram_gb: float = 6.0,
    ) -> RoamingDecision:
        """为算力任务计算路由决策."""
        nodes = {n.node_id: n for n in self.discovery.list_active_nodes()}
        local_node = nodes.get(self.local_node_id)

        # 1. 检查本地节点是否具备就地执行条件
        if local_node:
            if not local_node.is_throttled and local_node.vram_free_gb >= estimated_vram_gb:
                # P0 或 本地健康时优先本地就地执行
                return RoamingDecision(
                    job_id=job_id,
                    model_id=model_id,
                    priority=priority,
                    target_node_id=self.local_node_id,
                    target_endpoint=f"{local_node.host}:{local_node.port}",
                    is_roamed=False,
                    decision_reason=f"本地节点资源充足 (可用显存 {local_node.vram_free_gb}GB, 温度状态 {local_node.thermal_pressure})",
                    vram_budget_gb=estimated_vram_gb,
                )

        # 2. 本地受限或显存不足，发起局域网漫游调度
        best_peer = self.discovery.find_best_placement(model_id, priority=priority)
        if best_peer and best_peer.node_id != self.local_node_id:
            reason = "本地节点温度节流" if (local_node and local_node.is_throttled) else "本地显存不足，触发弹性溢出漫游"
            return RoamingDecision(
                job_id=job_id,
                model_id=model_id,
                priority=priority,
                target_node_id=best_peer.node_id,
                target_endpoint=f"{best_peer.host}:{best_peer.port}",
                is_roamed=True,
                decision_reason=f"{reason} ➜ 调度至远端对等节点 {best_peer.node_id}",
                vram_budget_gb=estimated_vram_gb,
            )

        # 3. 兜底本地降级排队
        endpoint = f"{local_node.host}:{local_node.port}" if local_node else "localhost:8765"
        return RoamingDecision(
            job_id=job_id,
            model_id=model_id,
            priority=priority,
            target_node_id=self.local_node_id,
            target_endpoint=endpoint,
            is_roamed=False,
            decision_reason="局域网无更优可用节点，降级本地等待队列执行",
            vram_budget_gb=estimated_vram_gb,
        )
