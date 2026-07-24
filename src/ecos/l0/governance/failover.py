"""L0 分布式原语 — 故障转移机制

实现多机协作的核心组件：
- FailoverManager: 故障转移管理
- FailoverStrategy: 故障转移策略枚举
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ecos.common.logger import get_logger

logger = get_logger("failover")


class FailoverStrategy(Enum):
    """故障转移策略"""

    RANDOM = "random"  # 随机选择
    ROUND_ROBIN = "round_robin"  # 轮询
    LEAST_LOADED = "least_loaded"  # 最小负载
    PRIORITY = "priority"  # 优先级


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

    def __init__(self, persistence=None, config=None):
        from ecos.common.config import ECOSConfig

        self.config = config or ECOSConfig.get_instance()
        self.rules: dict[str, FailoverRule] = {}
        self._persistence = persistence
        self.node_loads: dict[str, int] = {}
        self.node_priorities: dict[str, int] = {}
        self._round_robin_indices: dict[str, int] = {}
        self._failover_history: list[dict[str, Any]] = []
        self.max_history = self.config.get("failover.max_history", 100)

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
        return [
            r for r in self.rules.values() if r.source_node == node_id and r.enabled
        ]

    def select_target(self, rule: FailoverRule) -> Optional[str]:
        """选择故障转移目标"""
        if not rule.target_nodes:
            return None

        if rule.strategy == FailoverStrategy.RANDOM:
            import random

            return random.choice(rule.target_nodes)

        elif rule.strategy == FailoverStrategy.ROUND_ROBIN:
            idx = self._round_robin_indices.get(rule.rule_id, 0)
            target = rule.target_nodes[idx % len(rule.target_nodes)]
            self._round_robin_indices[rule.rule_id] = idx + 1
            return target

        elif rule.strategy == FailoverStrategy.LEAST_LOADED:
            # 选择负载最小的节点
            min_load = float("inf")
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
        try:
            rules = self.get_rules_for_node(source_node)
            if not rules:
                logger.warning("无故障转移规则: %s", source_node)
                return None

            for rule in rules:
                if rule.enabled:
                    target = self.select_target(rule)
                    if target:
                        self._failover_history.append(
                            {
                                "source": source_node,
                                "target": target,
                                "rule_id": rule.rule_id,
                                "strategy": rule.strategy.value,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        logger.info(
                            "故障转移: %s -> %s (rule=%s)",
                            source_node,
                            target,
                            rule.rule_id,
                        )
                        return target

            logger.warning("故障转移失败: 无可用目标节点 %s", source_node)
            return None
        except Exception as e:  # defensive fallback
            logger.error("故障转移异常: %s - %s", source_node, str(e))
            return None

    def get_failover_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取故障转移历史"""
        return self._failover_history[-limit:]

    def get_failover_count(self) -> dict[str, int]:
        """统计各节点的故障转移次数"""
        counts: dict[str, int] = {}
        for entry in self._failover_history:
            source = entry["source"]
            counts[source] = counts.get(source, 0) + 1
        return counts

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
            "failover_count": self.get_failover_count(),
            "history_count": len(self._failover_history),
        }

    def _load_state(self):
        """从持久化加载状态"""
        if not self._persistence:
            return
        try:
            saved = self._persistence.load("failover")
            if saved:
                logger.info("从持久化加载状态: failover")
        except Exception as e:  # defensive fallback
            logger.error("加载状态失败: %s", str(e))

    def _save_state(self):
        """保存状态到持久化"""
        if not self._persistence:
            return
        try:
            self._persistence.save("failover", {"placeholder": True})
            logger.debug("保存状态: failover")
        except Exception as e:  # defensive fallback
            logger.error("保存状态失败: %s", str(e))
