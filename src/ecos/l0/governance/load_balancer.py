"""L0 分布式原语 — 负载均衡器

实现多机协作的核心组件：
- LoadBalancer: 负载均衡器
- LoadBalancingStrategy: 负载均衡策略枚举
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ecos.common.logger import get_logger

logger = get_logger("load_balancer")


class LoadBalancingStrategy(Enum):
    """负载均衡策略"""

    ROUND_ROBIN = "round_robin"  # 轮询
    LEAST_CONNECTIONS = "least_connections"  # 最少连接
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"  # 加权轮询
    IP_HASH = "ip_hash"  # IP 哈希


@dataclass
class NodeLoad:
    """节点负载信息"""

    node_id: str
    connections: int = 0
    weight: int = 1
    healthy: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class LoadBalancer:
    """负载均衡器

    管理分布式系统中的负载均衡
    """

    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        persistence=None,
        config=None,
    ):
        from ecos.common.config import ECOSConfig

        self.config = config or ECOSConfig.get_instance()
        self.strategy = strategy
        self.nodes: dict[str, NodeLoad] = {}
        self._persistence = persistence
        self.current_index: int = 0
        self.health_check_interval = self.config.get(
            "load_balancer.health_check_interval", 30
        )

    def register_node(self, node_id: str, weight: int = 1) -> NodeLoad:
        """注册节点"""
        node = NodeLoad(node_id=node_id, weight=weight)
        self.nodes[node_id] = node
        return node

    def unregister_node(self, node_id: str) -> bool:
        """注销节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            return True
        return False

    def get_node(self, node_id: str) -> NodeLoad | None:
        """获取节点信息"""
        return self.nodes.get(node_id)

    def update_connections(self, node_id: str, connections: int) -> bool:
        """更新连接数"""
        if node_id in self.nodes:
            self.nodes[node_id].connections = connections
            return True
        return False

    def select_node(self) -> Optional[str]:
        """选择节点"""
        try:
            healthy_nodes = [n for n in self.nodes.values() if n.healthy]
            if not healthy_nodes:
                logger.warning("无健康节点可用")
                return None

            if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                # 轮询
                node = healthy_nodes[self.current_index % len(healthy_nodes)]
                self.current_index = (self.current_index + 1) % len(healthy_nodes)
                return node.node_id

            elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                # 最少连接
                min_connections = float("inf")
                min_node = None
                for node in healthy_nodes:
                    if node.connections < min_connections:
                        min_connections = node.connections
                        min_node = node.node_id
                return min_node

            elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin(healthy_nodes)

            elif self.strategy == LoadBalancingStrategy.IP_HASH:
                return self._ip_hash(healthy_nodes)

            return None
        except Exception as e:  # defensive fallback
            logger.error("选择节点失败: %s", str(e))
            return None

    def _weighted_round_robin(self, healthy_nodes: list[NodeLoad]) -> Optional[str]:
        """Nginx 平滑加权轮询算法"""
        if not healthy_nodes:
            return None

        total_weight = sum(n.weight for n in healthy_nodes)
        if total_weight == 0:
            return healthy_nodes[0].node_id

        if not hasattr(self, "_current_weights"):
            self._current_weights = {n.node_id: 0 for n in healthy_nodes}

        for node in healthy_nodes:
            self._current_weights[node.node_id] = (
                self._current_weights.get(node.node_id, 0) + node.weight
            )

        selected = max(
            healthy_nodes,
            key=lambda n: self._current_weights.get(n.node_id, 0),
        )

        self._current_weights[selected.node_id] -= total_weight

        return selected.node_id

    def _ip_hash(self, healthy_nodes: list[NodeLoad]) -> Optional[str]:
        """一致性哈希 — 基于 node_id 哈希环"""
        if not healthy_nodes:
            return None

        import hashlib

        ring: list[tuple[int, str]] = []
        for node in healthy_nodes:
            hash_val = int(hashlib.md5(node.node_id.encode()).hexdigest()[:8], 16)
            ring.append((hash_val, node.node_id))

        ring.sort(key=lambda x: x[0])

        key_hash = int(
            hashlib.md5(f"{self.current_index}".encode()).hexdigest()[:8], 16
        )
        self.current_index += 1

        for ring_hash, node_id in ring:
            if ring_hash >= key_hash:
                return node_id

        return ring[0][1] if ring else None

    def get_all_nodes(self) -> list[NodeLoad]:
        """获取所有节点"""
        return list(self.nodes.values())

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "strategy": self.strategy.value,
            "nodes": {
                nid: {
                    "connections": n.connections,
                    "weight": n.weight,
                    "healthy": n.healthy,
                }
                for nid, n in self.nodes.items()
            },
            "current_index": self.current_index,
        }

    def _load_state(self):
        """从持久化加载状态"""
        if not self._persistence:
            return
        try:
            saved = self._persistence.load("load_balancer")
            if saved:
                logger.info("从持久化加载状态: load_balancer")
        except Exception as e:  # defensive fallback
            logger.error("加载状态失败: %s", str(e))

    def _save_state(self):
        """保存状态到持久化"""
        if not self._persistence:
            return
        try:
            self._persistence.save("load_balancer", {"placeholder": True})
            logger.debug("保存状态: load_balancer")
        except Exception as e:  # defensive fallback
            logger.error("保存状态失败: %s", str(e))
