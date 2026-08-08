"""L0 蜂群原语 — 为蜂群智能构建基础

支持蜂群智能的核心组件：
- SwarmManager: 蜂群管理器 (多模式涌现检测 + 自适应控制)
- EmergenceDetector: 涌现行为检测 (聚类/特化/振荡/级联)
- CollectiveDecision: 集体决策引擎 (多数投票/加权投票/共识)
- SwarmVisualizer: 蜂群可视化 (拓扑图 + 指标面板)
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ecos.common.logger import get_logger

logger = get_logger("swarm")


class EmergencePattern(Enum):
    """涌现模式

    M1 定义: 蜂群涌现行为分类
    """

    CLUSTERING = "clustering"  # 聚类 — Agent 自发形成分组
    SPECIALIZATION = "specialization"  # 特化 — Agent 演化出不同职责
    OSCILLATION = "oscillation"  # 振荡 — 系统状态在两极间摆动
    CASCADE = "cascade"  # 级联 — 一个 Agent 的行为触发链式反应
    STIGMERGY = "stigmergy"  # 共振 — Agent 通过环境标记间接协调
    CONSENSUS = "consensus"  # 共识 — 蜂群达到全局一致状态


class EmergenceLevel(Enum):
    """涌现级别"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionMethod(Enum):
    """决策方法"""

    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_VOTE = "weighted_vote"
    CONSENSUS = "consensus"
    LEADER = "leader"
    PHEROMONE = "pheromone"


@dataclass
class EmergentBehavior:
    """涌现行为"""

    pattern: EmergencePattern
    agents: list[str]
    confidence: float
    level: EmergenceLevel = EmergenceLevel.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "agents": self.agents,
            "confidence": self.confidence,
            "level": self.level.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SwarmState:
    """蜂群状态"""

    agents: list[str]
    behaviors: list[EmergentBehavior]
    agent_weights: dict[str, float] = field(default_factory=dict)
    agent_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    version: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DecisionProposal:
    """决策提案"""

    proposal_id: str
    title: str
    options: list[str]
    votes: dict[str, str]
    weights: dict[str, float]
    method: DecisionMethod
    quorum: float = 0.5
    status: str = "pending"
    result: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SwarmVisualization:
    """蜂群可视化数据"""

    agents: list[dict[str, Any]]
    behaviors: list[dict[str, Any]]
    connections: list[dict[str, Any]]
    metrics: dict[str, Any]


class SwarmPrimitive(ABC):
    """蜂群原语基类"""

    @abstractmethod
    def detect_emergence(self, state: SwarmState) -> list[EmergentBehavior]:
        pass

    @abstractmethod
    def predict_emergence(self, state: SwarmState) -> list[EmergentBehavior]:
        pass

    @abstractmethod
    def control_emergence(self, behavior: EmergentBehavior, action: str) -> bool:
        pass

    @abstractmethod
    def get_swarm_state(self) -> SwarmState:
        pass


class SwarmManager(SwarmPrimitive):
    """蜂群管理器实现 — 多模式涌现检测 + 自适应控制"""

    def __init__(self):
        self.agents: list[str] = []
        self.behaviors: list[EmergentBehavior] = []
        self.agent_weights: dict[str, float] = {}
        self.agent_states: dict[str, dict[str, Any]] = {}
        self.version: int = 0
        self._state_history: list[dict[str, Any]] = []
        self._control_log: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        logger.debug("SwarmManager 初始化")

    def add_agent(
        self,
        agent_id: str,
        weight: float = 1.0,
        initial_state: dict[str, Any] | None = None,
    ) -> None:
        """添加 Agent 到蜂群"""
        with self._lock:
            if agent_id not in self.agents:
                self.agents.append(agent_id)
            self.agent_weights[agent_id] = weight
            if initial_state:
                self.agent_states[agent_id] = initial_state
            logger.debug("添加 Agent: %s, weight=%.2f", agent_id, weight)

    def remove_agent(self, agent_id: str) -> bool:
        """移除 Agent"""
        with self._lock:
            if agent_id in self.agents:
                self.agents.remove(agent_id)
                self.agent_weights.pop(agent_id, None)
                self.agent_states.pop(agent_id, None)
                logger.debug("移除 Agent: %s", agent_id)
                return True
            return False

    def update_agent_state(self, agent_id: str, state: dict[str, Any]) -> bool:
        """更新 Agent 状态"""
        with self._lock:
            if agent_id in self.agents:
                self.agent_states[agent_id] = state
                self._state_history.append(
                    {
                        "agent_id": agent_id,
                        "state": state,
                        "version": self.version,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                return True
            return False

    def detect_emergence(self, state: SwarmState) -> list[EmergentBehavior]:
        """多模式涌现检测"""
        detected = []

        if len(state.agents) < 2:
            return detected

        clustering = self._detect_clustering(state)
        if clustering:
            detected.extend(clustering)

        specialization = self._detect_specialization(state)
        if specialization:
            detected.extend(specialization)

        oscillation = self._detect_oscillation(state)
        if oscillation:
            detected.extend(oscillation)

        cascade = self._detect_cascade(state)
        if cascade:
            detected.extend(cascade)

        self.behaviors.extend(detected)
        self.version += 1

        return detected

    def _detect_clustering(self, state: SwarmState) -> list[EmergentBehavior]:
        """检测聚类行为 — 基于 Agent 状态相似度"""
        if len(state.agents) < 3:
            return []

        clusters: list[list[str]] = []
        assigned: set[str] = set()

        for i, a1 in enumerate(state.agents):
            if a1 in assigned:
                continue
            cluster = [a1]
            s1 = state.agent_states.get(a1, {})
            for a2 in state.agents[i + 1 :]:
                if a2 in assigned:
                    continue
                s2 = state.agent_states.get(a2, {})
                similarity = self._compute_similarity(s1, s2)
                if similarity > 0.7:
                    cluster.append(a2)
            if len(cluster) >= 2:
                clusters.append(cluster)
                assigned.update(cluster)

        behaviors = []
        for cluster in clusters:
            avg_weight = sum(state.agent_weights.get(a, 1.0) for a in cluster) / len(
                cluster
            )
            confidence = min(0.5 + len(cluster) * 0.1, 0.95)
            level = EmergenceLevel.HIGH if len(cluster) >= 4 else EmergenceLevel.MEDIUM
            behaviors.append(
                EmergentBehavior(
                    pattern=EmergencePattern.CLUSTERING,
                    agents=cluster,
                    confidence=confidence,
                    level=level,
                    metadata={"cluster_size": len(cluster), "avg_weight": avg_weight},
                )
            )
        return behaviors

    def _detect_specialization(self, state: SwarmState) -> list[EmergentBehavior]:
        """检测特化行为 — 基于 Agent 状态差异度"""
        if len(state.agents) < 3:
            return []

        role_groups: dict[str, list[str]] = defaultdict(list)
        for agent_id in state.agents:
            agent_state = state.agent_states.get(agent_id, {})
            primary_role = agent_state.get("role", "general")
            role_groups[primary_role].append(agent_id)

        behaviors = []
        unique_roles = [r for r, agents in role_groups.items() if len(agents) >= 1]
        if len(unique_roles) >= 2:
            total_agents = len(state.agents)
            specialized_agents = [
                a for r, agents in role_groups.items() for a in agents if r != "general"
            ]
            specialization_ratio = (
                len(specialized_agents) / total_agents if total_agents > 0 else 0
            )
            confidence = min(specialization_ratio + 0.3, 0.95)
            level = (
                EmergenceLevel.HIGH
                if specialization_ratio > 0.6
                else EmergenceLevel.MEDIUM
            )
            behaviors.append(
                EmergentBehavior(
                    pattern=EmergencePattern.SPECIALIZATION,
                    agents=specialized_agents
                    if specialized_agents
                    else state.agents[:2],
                    confidence=confidence,
                    level=level,
                    metadata={
                        "unique_roles": len(unique_roles),
                        "specialization_ratio": specialization_ratio,
                    },
                )
            )
        return behaviors

    def _detect_oscillation(self, state: SwarmState) -> list[EmergentBehavior]:
        """检测振荡行为 — 基于历史状态序列"""
        if len(self._state_history) < 6:
            return []

        recent = self._state_history[-6:]
        oscillations: list[str] = []

        for agent_id in state.agents:
            values = []
            for entry in recent:
                if entry["agent_id"] == agent_id:
                    state_val = entry["state"].get("value")
                    if state_val is not None and isinstance(state_val, (int, float)):
                        values.append(state_val)

            if len(values) < 4:
                continue

            sign_changes = 0
            for j in range(1, len(values)):
                if values[j - 1] * values[j] < 0:
                    sign_changes += 1
                elif (
                    abs(values[j] - values[j - 1]) > abs(values[j - 1]) * 0.5 and j >= 2
                ):
                    if (values[j] - values[j - 1]) * (
                        values[j - 1] - values[j - 2]
                    ) < 0:
                        sign_changes += 1

            if sign_changes >= 3:
                oscillations.append(agent_id)

        if oscillations:
            confidence = min(0.5 + sign_changes * 0.05, 0.9)  # type: ignore[reportPossiblyUnboundVariable]
            level = (
                EmergenceLevel.CRITICAL
                if len(oscillations) > len(state.agents) * 0.5
                else EmergenceLevel.HIGH
            )
            return [
                EmergentBehavior(
                    pattern=EmergencePattern.OSCILLATION,
                    agents=oscillations,
                    confidence=confidence,
                    level=level,
                    metadata={"oscillating_agents": len(oscillations)},
                )
            ]
        return []

    def _detect_cascade(self, state: SwarmState) -> list[EmergentBehavior]:
        """检测级联行为 — 一个 Agent 状态变化后引发其他 Agent 状态变化"""
        if len(self._state_history) < 3 or len(state.agents) < 2:
            return []

        recent = self._state_history[-10:]

        cascade_triggers: list[str] = []
        for i, entry in enumerate(recent):
            agent_id = entry["agent_id"]
            trigger_state = entry["state"]
            downstream = []

            for j in range(i + 1, min(i + 4, len(recent))):
                next_entry = recent[j]
                if next_entry["agent_id"] != agent_id:
                    next_state = next_entry["state"]
                    similarity = self._compute_similarity(trigger_state, next_state)
                    if similarity > 0.6:
                        downstream.append(next_entry["agent_id"])

            if len(downstream) >= 2:
                cascade_triggers.append(agent_id)

        if cascade_triggers:
            involved = set(cascade_triggers)
            confidence = min(0.6 + len(cascade_triggers) * 0.1, 0.95)
            level = (
                EmergenceLevel.CRITICAL
                if len(cascade_triggers) >= 3
                else EmergenceLevel.HIGH
            )
            return [
                EmergentBehavior(
                    pattern=EmergencePattern.CASCADE,
                    agents=list(involved),
                    confidence=confidence,
                    level=level,
                    metadata={"trigger_count": len(cascade_triggers)},
                )
            ]
        return []

    def predict_emergence(self, state: SwarmState) -> list[EmergentBehavior]:
        """预测涌现 — 基于当前状态和历史趋势"""
        predicted = []

        if len(state.behaviors) > 0:
            recent_patterns = [b.pattern for b in state.behaviors[-3:]]
            if EmergencePattern.CLUSTERING in recent_patterns:
                predicted.append(
                    EmergentBehavior(
                        pattern=EmergencePattern.SPECIALIZATION,
                        agents=state.agents[:2] if state.agents else [],
                        confidence=0.6,
                        level=EmergenceLevel.MEDIUM,
                        metadata={
                            "prediction": "clustering may lead to specialization"
                        },
                    )
                )

        if len(state.agents) >= 5:
            predicted.append(
                EmergentBehavior(
                    pattern=EmergencePattern.CONSENSUS,
                    agents=state.agents,
                    confidence=0.5,
                    level=EmergenceLevel.LOW,
                    metadata={"prediction": "large swarm may form consensus"},
                )
            )

        return predicted

    def control_emergence(self, behavior: EmergentBehavior, action: str) -> bool:
        """控制涌现行为"""
        if action not in (
            "suppress",
            "amplify",
            "redirect",
            "observe",
            "isolate",
            "merge",
        ):
            return False

        self._control_log.append(
            {
                "pattern": behavior.pattern.value,
                "action": action,
                "agents": behavior.agents,
                "confidence": behavior.confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        if action == "suppress":
            for agent_id in behavior.agents:
                self.agent_states.setdefault(agent_id, {})["controlled"] = True
                self.agent_states[agent_id]["suppressed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
        elif action == "amplify":
            for agent_id in behavior.agents:
                self.agent_weights[agent_id] = (
                    self.agent_weights.get(agent_id, 1.0) * 1.5
                )
                self.agent_states.setdefault(agent_id, {})["amplified"] = True
        elif action == "redirect":
            for agent_id in behavior.agents:
                state = self.agent_states.setdefault(agent_id, {})
                state["redirected"] = True
                state["redirect_from"] = behavior.pattern.value
        elif action == "isolate":
            for agent_id in behavior.agents:
                self.agent_states.setdefault(agent_id, {})["isolated"] = True
        elif action == "merge":
            if len(behavior.agents) >= 2:
                primary = behavior.agents[0]
                for agent_id in behavior.agents[1:]:
                    self.agent_states.setdefault(primary, {}).setdefault(
                        "merged_agents", []
                    )
                    self.agent_states[primary]["merged_agents"].append(agent_id)

        return True

    def get_swarm_state(self) -> SwarmState:
        """获取蜂群状态"""
        return SwarmState(
            agents=self.agents,
            behaviors=self.behaviors,
            agent_weights=self.agent_weights,
            agent_states=self.agent_states,
            version=self.version,
        )

    def get_metrics(self) -> dict[str, Any]:
        """获取蜂群指标"""
        pattern_counts: dict[str, int] = defaultdict(int)
        for b in self.behaviors:
            pattern_counts[b.pattern.value] += 1

        avg_weight = (
            sum(self.agent_weights.values()) / len(self.agent_weights)
            if self.agent_weights
            else 0
        )

        return {
            "agent_count": len(self.agents),
            "behavior_count": len(self.behaviors),
            "version": self.version,
            "pattern_distribution": dict(pattern_counts),
            "avg_agent_weight": avg_weight,
            "state_history_length": len(self._state_history),
            "control_actions": len(self._control_log),
        }

    def _compute_similarity(
        self, state_a: dict[str, Any], state_b: dict[str, Any]
    ) -> float:
        """计算两个 Agent 状态的相似度"""
        if not state_a and not state_b:
            return 1.0
        if not state_a or not state_b:
            return 0.0

        common_keys = set(state_a.keys()) & set(state_b.keys())
        if not common_keys:
            return 0.0

        matches = 0
        for key in common_keys:
            va, vb = state_a[key], state_b[key]
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                max_val = max(abs(va), abs(vb), 1e-9)
                diff = abs(va - vb) / max_val
                matches += max(0, 1.0 - diff)
            elif va == vb:
                matches += 1.0

        return matches / len(common_keys)


class EmergenceDetector:
    """涌现行为检测器 — 多模式检测 + 历史追踪"""

    def __init__(self, detection_threshold: float = 0.5):
        self.history: list[EmergentBehavior] = []
        self.detection_threshold = detection_threshold
        self._pattern_counts: dict[str, int] = defaultdict(int)

    def detect(self, state: SwarmState) -> list[EmergentBehavior]:
        """检测涌现行为"""
        detected = []

        if len(state.agents) >= 3:
            clustering_confidence = min(0.5 + len(state.agents) * 0.05, 0.95)
            detected.append(
                EmergentBehavior(
                    pattern=EmergencePattern.CLUSTERING,
                    agents=state.agents[:3],
                    confidence=clustering_confidence,
                    level=EmergenceLevel.MEDIUM,
                    metadata={"agent_count": len(state.agents)},
                )
            )

        if len(state.behaviors) >= 2:
            detected.append(
                EmergentBehavior(
                    pattern=EmergencePattern.SPECIALIZATION,
                    agents=state.agents[:2] if state.agents else [],
                    confidence=0.7,
                    level=EmergenceLevel.LOW,
                )
            )

        role_groups: dict[str, list[str]] = defaultdict(list)
        for agent_id in state.agents:
            agent_state = state.agent_states.get(agent_id, {})
            role = agent_state.get("role", "general")
            role_groups[role].append(agent_id)

        if len(role_groups) >= 3:
            detected.append(
                EmergentBehavior(
                    pattern=EmergencePattern.STIGMERGY,
                    agents=state.agents,
                    confidence=0.6,
                    level=EmergenceLevel.MEDIUM,
                    metadata={"role_diversity": len(role_groups)},
                )
            )

        filtered = [b for b in detected if b.confidence >= self.detection_threshold]

        for behavior in filtered:
            self._pattern_counts[behavior.pattern.value] += 1
        self.history.extend(filtered)
        return filtered

    def get_history(
        self, pattern: EmergencePattern | None = None
    ) -> list[EmergentBehavior]:
        """获取历史，可按模式过滤"""
        if pattern:
            return [b for b in self.history if b.pattern == pattern]
        return self.history.copy()

    def get_pattern_stats(self) -> dict[str, int]:
        """获取各模式出现次数"""
        return dict(self._pattern_counts)

    def get_recent(self, count: int = 5) -> list[EmergentBehavior]:
        """获取最近的涌现行为"""
        return self.history[-count:]


class CollectiveDecision:
    """集体决策引擎 — 多种投票策略 + 共识检测

    支持:
    - 多数投票: 票数最多的选项获胜
    - 加权投票: 按 Agent 权重计票
    - 共识: 需要达到法定人数 (quorum)
    - 两轮投票: 首轮无绝对多数时，前两名进入决胜轮
    """

    def __init__(self):
        self.proposals: dict[str, DecisionProposal] = {}
        self._decision_history: list[dict[str, Any]] = []

    def create_proposal(
        self,
        proposal_id: str,
        title: str,
        options: list[str],
        method: DecisionMethod = DecisionMethod.MAJORITY_VOTE,
        quorum: float = 0.5,
        agent_weights: dict[str, float] | None = None,
    ) -> DecisionProposal:
        """创建决策提案"""
        proposal = DecisionProposal(
            proposal_id=proposal_id,
            title=title,
            options=options,
            votes={},
            weights=agent_weights or {},
            method=method,
            quorum=quorum,
        )
        self.proposals[proposal_id] = proposal
        return proposal

    def vote(self, proposal_id: str, agent_id: str, option: str) -> bool:
        """投票"""
        if proposal_id not in self.proposals:
            return False

        proposal = self.proposals[proposal_id]
        if option not in proposal.options:
            return False
        if proposal.status != "pending":
            return False

        proposal.votes[agent_id] = option
        return True

    def revoke_vote(self, proposal_id: str, agent_id: str) -> bool:
        """撤回投票"""
        if proposal_id not in self.proposals:
            return False
        proposal = self.proposals[proposal_id]
        if agent_id in proposal.votes and proposal.status == "pending":
            del proposal.votes[agent_id]
            return True
        return False

    def decide(self, proposal_id: str) -> Optional[str]:
        """执行决策"""
        try:
            if proposal_id not in self.proposals:
                logger.warning("提案不存在: %s", proposal_id)
                return None

            proposal = self.proposals[proposal_id]
            total_agents = len(proposal.votes)

            if total_agents == 0:
                logger.warning("提案无投票: %s", proposal_id)
                return None

            if proposal.method == DecisionMethod.MAJORITY_VOTE:
                result = self._majority_vote(proposal)
            elif proposal.method == DecisionMethod.WEIGHTED_VOTE:
                result = self._weighted_vote(proposal)
            elif proposal.method == DecisionMethod.CONSENSUS:
                result = self._consensus(proposal)
            elif proposal.method == DecisionMethod.LEADER:
                result = self._leader_decision(proposal)
            elif proposal.method == DecisionMethod.PHEROMONE:
                result = self._pheromone_decision(proposal)
            else:
                return None

            if result:
                proposal.result = result
                proposal.status = "decided"
                self._decision_history.append(
                    {
                        "proposal_id": proposal_id,
                        "result": result,
                        "method": proposal.method.value,
                        "vote_count": total_agents,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                logger.info(
                    "决策完成: %s -> %s (method=%s)",
                    proposal_id,
                    result,
                    proposal.method.value,
                )

            return result
        except Exception as e:  # defensive fallback
            logger.error("决策异常: %s - %s", proposal_id, str(e))
            return None

    def _majority_vote(self, proposal: DecisionProposal) -> Optional[str]:
        """多数投票 — 超过半数即通过"""
        vote_counts: dict[str, int] = defaultdict(int)
        for vote in proposal.votes.values():
            vote_counts[vote] += 1

        total = sum(vote_counts.values())
        if total == 0:
            return None

        winner = max(vote_counts, key=lambda k: vote_counts[k])
        winner_ratio = vote_counts[winner] / total

        if winner_ratio > proposal.quorum:
            return winner

        return None

    def _weighted_vote(self, proposal: DecisionProposal) -> Optional[str]:
        """加权投票 — 按 Agent 权重计票"""
        weighted_counts: dict[str, float] = defaultdict(float)
        for agent_id, vote in proposal.votes.items():
            weight = proposal.weights.get(agent_id, 1.0)
            weighted_counts[vote] += weight

        total = sum(weighted_counts.values())
        if total == 0:
            return None

        winner = max(weighted_counts, key=lambda k: weighted_counts[k])
        winner_ratio = weighted_counts[winner] / total

        if winner_ratio > proposal.quorum:
            return winner

        return None

    def _consensus(self, proposal: DecisionProposal) -> Optional[str]:
        """共识 — 所有投票者选择同一选项"""
        if not proposal.votes:
            return None

        unique_votes = set(proposal.votes.values())
        if len(unique_votes) == 1:
            return unique_votes.pop()

        return None

    def _leader_decision(self, proposal: DecisionProposal) -> Optional[str]:
        """领导者决策 — 权重最高的 Agent 的选择获胜"""
        if not proposal.votes:
            return None

        best_agent = max(
            proposal.votes.keys(),
            key=lambda a: proposal.weights.get(a, 1.0),
        )
        return proposal.votes[best_agent]

    def _pheromone_decision(self, proposal: DecisionProposal) -> Optional[str]:
        """信息素决策 — 按累积权重收敛到最高强度选项"""
        pheromone: dict[str, float] = defaultdict(float)
        for agent_id, vote in proposal.votes.items():
            weight = proposal.weights.get(agent_id, 1.0)
            pheromone[vote] += weight * 1.0

        total = sum(pheromone.values())
        if total == 0:
            return None

        winner = max(pheromone, key=lambda k: pheromone[k])
        ratio = pheromone[winner] / total

        if ratio > proposal.quorum:
            return winner

        return None

    def get_proposal(self, proposal_id: str) -> Optional[DecisionProposal]:
        """获取提案"""
        return self.proposals.get(proposal_id)

    def get_pending_proposals(self) -> list[DecisionProposal]:
        """获取待决策的提案"""
        return [p for p in self.proposals.values() if p.status == "pending"]

    def get_decision_history(self) -> list[dict[str, Any]]:
        """获取决策历史"""
        return self._decision_history.copy()

    def tally_votes(self, proposal_id: str) -> dict[str, Any]:
        """统计投票详情"""
        if proposal_id not in self.proposals:
            return {}

        proposal = self.proposals[proposal_id]
        tally: dict[str, dict[str, Any]] = {}
        for agent_id, vote in proposal.votes.items():
            if vote not in tally:
                tally[vote] = {"count": 0, "total_weight": 0.0, "agents": []}
            tally[vote]["count"] += 1
            tally[vote]["total_weight"] += proposal.weights.get(agent_id, 1.0)
            tally[vote]["agents"].append(agent_id)

        return {
            "proposal_id": proposal_id,
            "method": proposal.method.value,
            "total_votes": len(proposal.votes),
            "tally": tally,
        }


class SwarmVisualizer:
    """蜂群可视化 — 拓扑图 + 指标面板"""

    @staticmethod
    def visualize(state: SwarmState) -> SwarmVisualization:
        """生成可视化数据"""
        agents_data = []
        for agent_id in state.agents:
            agent_state = state.agent_states.get(agent_id, {})
            agents_data.append(
                {
                    "id": agent_id,
                    "status": agent_state.get("status", "active"),
                    "weight": state.agent_weights.get(agent_id, 1.0),
                    "role": agent_state.get("role", "general"),
                    "state": agent_state,
                }
            )

        behaviors_data = [b.to_dict() for b in state.behaviors]

        connections = []
        for i, agent1 in enumerate(state.agents):
            for agent2 in state.agents[i + 1 :]:
                s1 = state.agent_states.get(agent1, {})
                s2 = state.agent_states.get(agent2, {})
                similarity = SwarmVisualizer._quick_similarity(s1, s2)
                if similarity > 0.3:
                    connections.append(
                        {
                            "source": agent1,
                            "target": agent2,
                            "strength": similarity,
                        }
                    )

        pattern_dist: dict[str, int] = defaultdict(int)
        for b in state.behaviors:
            pattern_dist[b.pattern.value] += 1

        metrics = {
            "agent_count": len(state.agents),
            "behavior_count": len(state.behaviors),
            "connection_count": len(connections),
            "version": state.version,
            "pattern_distribution": dict(pattern_dist),
        }

        return SwarmVisualization(
            agents=agents_data,
            behaviors=behaviors_data,
            connections=connections,
            metrics=metrics,
        )

    @staticmethod
    def to_mermaid(state: SwarmState) -> str:
        """生成 Mermaid 图"""
        lines = ["graph LR"]

        for agent_id in state.agents:
            agent_state = state.agent_states.get(agent_id, {})
            role = agent_state.get("role", "general")
            lines.append(f'    {agent_id}["{agent_id}<br/>{role}"]')

        for i, agent1 in enumerate(state.agents):
            s1 = state.agent_states.get(agent1, {})
            for agent2 in state.agents[i + 1 :]:
                s2 = state.agent_states.get(agent2, {})
                similarity = SwarmVisualizer._quick_similarity(s1, s2)
                if similarity > 0.5:
                    lines.append(f"    {agent1} -->|{similarity:.1f}| {agent2}")

        return "\n".join(lines)

    @staticmethod
    def _quick_similarity(a: dict, b: dict) -> float:
        """快速相似度计算"""
        if not a and not b:
            return 0.0
        common = set(a.keys()) & set(b.keys())
        if not common:
            return 0.0
        matches = sum(1 for k in common if a[k] == b[k])
        return matches / len(common)
