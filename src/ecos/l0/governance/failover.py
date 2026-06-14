"""L0 分布式原语 — 故障转移机制

实现多机协作的核心组件：
- FailoverManager: 故障转移管理
- FailoverStrategy: 故障转移策略枚举
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FailoverStrategy(Enum):
    """故障转移策略"""
    RANDOM = "random"           # 随机选择
    ROUND_ROBIN = "round_robin" # 轮询
    LEAST_LOADED = "least_loaded"  # 最小负载
    PRIORITY = "priority"       # 优先级


@dataclass
class FailoverRule:
    """故障转移规则"""
    rule_id: str
    source_node: str
    target_nodes: list[str]
    strategy: FailoverStrategy
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class FailoverManager:
    """故障转移管理器
    
    管理分布式系统中的故障转移规则和执行
    """
    
    def __init__(self):
        self.rules: dict[str, FailoverRule] = {}
        self.node_loads: dict[str, int] = {}
        self.node_priorities: dict[str, int] = {}
    
    def add_rule(self, rule: FailoverRule) -> None:
        """添加故障转移规则"""
        self.rules[rule.rule_id] = rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """移除故障转移规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False
    
    def get_rule(self, rule_id: str) -> FailoverRule | None:
        """获取故障转移规则"""
        return self.rules.get(rule_id)
    
    def get_rules_for_node(self, node_id: str) -> list[FailoverRule]:
        """获取节点的故障转移规则"""
        return [r for r in self.rules.values() if r.source_node == node_id and r.enabled]
    
    def select_target(self, rule: FailoverRule) -> Optional[str]:
        """选择故障转移目标"""
        if not rule.target_nodes:
            return None
        
        if rule.strategy == FailoverStrategy.RANDOM:
            import random
            return random.choice(rule.target_nodes)
        
        elif rule.strategy == FailoverStrategy.ROUND_ROBIN:
            # 简单轮询：返回第一个目标
            return rule.target_nodes[0]
        
        elif rule.strategy == FailoverStrategy.LEAST_LOADED:
            # 选择负载最小的节点
            min_load = float('inf')
            min_node = None
            for node in rule.target_nodes:
                load = self.node_loads.get(node, 0)
                if load < min_load:
                    min_load = load
                    min_node = node
            return min_node
        
        elif rule.strategy == FailoverStrategy.PRIORITY:
            # 选择优先级最高的节点
            max_priority = -1
            max_node = None
            for node in rule.target_nodes:
                priority = self.node_priorities.get(node, 0)
                if priority > max_priority:
                    max_priority = priority
                    max_node = node
            return max_node
        
        return None
    
    def execute_failover(self, source_node: str) -> Optional[str]:
        """执行故障转移"""
        rules = self.get_rules_for_node(source_node)
        if not rules:
            return None
        
        # 使用第一个启用的规则
        for rule in rules:
            if rule.enabled:
                target = self.select_target(rule)
                if target:
                    return target
        
        return None
    
    def update_node_load(self, node_id: str, load: int) -> None:
        """更新节点负载"""
        self.node_loads[node_id] = load
    
    def update_node_priority(self, node_id: str, priority: int) -> None:
        """更新节点优先级"""
        self.node_priorities[node_id] = priority
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "rules": {
                rid: {
                    "source_node": r.source_node,
                    "target_nodes": r.target_nodes,
                    "strategy": r.strategy.value,
                    "enabled": r.enabled,
                }
                for rid, r in self.rules.items()
            },
            "node_loads": self.node_loads,
            "node_priorities": self.node_priorities,
        }
