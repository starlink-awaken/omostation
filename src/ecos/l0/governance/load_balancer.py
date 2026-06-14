"""L0 分布式原语 — 负载均衡器

实现多机协作的核心组件：
- LoadBalancer: 负载均衡器
- LoadBalancingStrategy: 负载均衡策略枚举
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class LoadBalancingStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"       # 轮询
    LEAST_CONNECTIONS = "least_connections"  # 最少连接
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"  # 加权轮询
    IP_HASH = "ip_hash"               # IP 哈希


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
    
    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN):
        self.strategy = strategy
        self.nodes: dict[str, NodeLoad] = {}
        self.current_index: int = 0
    
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
        healthy_nodes = [n for n in self.nodes.values() if n.healthy]
        if not healthy_nodes:
            return None
        
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            # 轮询
            node = healthy_nodes[self.current_index % len(healthy_nodes)]
            self.current_index = (self.current_index + 1) % len(healthy_nodes)
            return node.node_id
        
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            # 最少连接
            min_connections = float('inf')
            min_node = None
            for node in healthy_nodes:
                if node.connections < min_connections:
                    min_connections = node.connections
                    min_node = node.node_id
            return min_node
        
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            # 加权轮询
            total_weight = sum(n.weight for n in healthy_nodes)
            if total_weight == 0:
                return None
            
            # 简化实现：返回权重最大的节点
            max_weight = 0
            max_node = None
            for node in healthy_nodes:
                if node.weight > max_weight:
                    max_weight = node.weight
                    max_node = node.node_id
            return max_node
        
        elif self.strategy == LoadBalancingStrategy.IP_HASH:
            # IP 哈希 (简化：使用 node_id 哈希)
            if healthy_nodes:
                hash_value = hash(datetime.now().isoformat()) % len(healthy_nodes)
                return healthy_nodes[hash_value].node_id
        
        return None
    
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
