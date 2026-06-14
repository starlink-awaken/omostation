"""L0 蜂群原语 — 为蜂群智能构建基础

支持蜂群智能的核心组件：
- SwarmManager: 蜂群管理器
- EmergenceDetector: 涌现行为检测
- CollectiveDecision: 集体决策引擎
- SwarmVisualizer: 蜂群可视化
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EmergencePattern(Enum):
    """涌现模式
    
    M1 定义: 蜂群涌现行为分类
    """
    CLUSTERING = "clustering"          # 聚类
    SPECIALIZATION = "specialization"  # 特化
    OSCILLATION = "oscillation"        # 振荡
    CASCADE = "cascade"                # 级联


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
    version: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DecisionProposal:
    """决策提案"""
    proposal_id: str
    title: str
    options: list[str]
    votes: dict[str, str]
    method: DecisionMethod
    status: str = "pending"
    result: Optional[str] = None


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
        """检测涌现"""
        pass
    
    @abstractmethod
    def predict_emergence(self, state: SwarmState) -> list[EmergentBehavior]:
        """预测涌现"""
        pass
    
    @abstractmethod
    def control_emergence(self, behavior: EmergentBehavior, action: str) -> bool:
        """控制涌现"""
        pass
    
    @abstractmethod
    def get_swarm_state(self) -> SwarmState:
        """获取蜂群状态"""
        pass


class SwarmManager(SwarmPrimitive):
    """蜂群管理器实现"""
    
    def __init__(self):
        self.agents: list[str] = []
        self.behaviors: list[EmergentBehavior] = []
        self.version: int = 0
    
    def detect_emergence(self, state: SwarmState) -> list[EmergentBehavior]:
        """检测涌现"""
        detected = []
        if len(state.agents) >= 3:
            detected.append(EmergentBehavior(
                pattern=EmergencePattern.CLUSTERING,
                agents=state.agents[:3],
                confidence=0.8,
            ))
        return detected
    
    def predict_emergence(self, state: SwarmState) -> list[EmergentBehavior]:
        """预测涌现"""
        predicted = []
        if len(state.behaviors) > 0:
            predicted.append(EmergentBehavior(
                pattern=EmergencePattern.SPECIALIZATION,
                agents=state.agents[:2] if state.agents else [],
                confidence=0.6,
            ))
        return predicted
    
    def control_emergence(self, behavior: EmergentBehavior, action: str) -> bool:
        """控制涌现"""
        return True
    
    def get_swarm_state(self) -> SwarmState:
        """获取蜂群状态"""
        return SwarmState(
            agents=self.agents,
            behaviors=self.behaviors,
            version=self.version,
        )


class EmergenceDetector:
    """涌现行为检测器"""
    
    def __init__(self):
        self.history: list[EmergentBehavior] = []
    
    def detect(self, state: SwarmState) -> list[EmergentBehavior]:
        """检测涌现行为"""
        detected = []
        
        # 检测聚类
        if len(state.agents) >= 3:
            detected.append(EmergentBehavior(
                pattern=EmergencePattern.CLUSTERING,
                agents=state.agents[:3],
                confidence=0.8,
                level=EmergenceLevel.MEDIUM,
            ))
        
        # 检测特化
        if len(state.behaviors) >= 2:
            detected.append(EmergentBehavior(
                pattern=EmergencePattern.SPECIALIZATION,
                agents=state.agents[:2] if state.agents else [],
                confidence=0.7,
                level=EmergenceLevel.LOW,
            ))
        
        self.history.extend(detected)
        return detected
    
    def get_history(self) -> list[EmergentBehavior]:
        """获取历史"""
        return self.history.copy()


class CollectiveDecision:
    """集体决策引擎"""
    
    def __init__(self):
        self.proposals: dict[str, DecisionProposal] = {}
    
    def create_proposal(self, proposal_id: str, title: str, options: list[str],
                        method: DecisionMethod = DecisionMethod.MAJORITY_VOTE) -> DecisionProposal:
        """创建决策提案"""
        proposal = DecisionProposal(
            proposal_id=proposal_id,
            title=title,
            options=options,
            votes={},
            method=method,
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
        
        proposal.votes[agent_id] = option
        return True
    
    def decide(self, proposal_id: str) -> Optional[str]:
        """决策"""
        if proposal_id not in self.proposals:
            return None
        
        proposal = self.proposals[proposal_id]
        
        if proposal.method == DecisionMethod.MAJORITY_VOTE:
            # 多数投票
            vote_counts: dict[str, int] = {}
            for vote in proposal.votes.values():
                vote_counts[vote] = vote_counts.get(vote, 0) + 1
            
            if vote_counts:
                result = max(vote_counts, key=vote_counts.get)
                proposal.result = result
                proposal.status = "decided"
                return result
        
        elif proposal.method == DecisionMethod.CONSENSUS:
            # 共识：所有投票相同
            votes = list(proposal.votes.values())
            if len(votes) > 1 and len(set(votes)) == 1:
                proposal.result = votes[0]
                proposal.status = "decided"
                return votes[0]
        
        return None
    
    def get_proposal(self, proposal_id: str) -> Optional[DecisionProposal]:
        """获取提案"""
        return self.proposals.get(proposal_id)


class SwarmVisualizer:
    """蜂群可视化"""
    
    @staticmethod
    def visualize(state: SwarmState) -> SwarmVisualization:
        """生成可视化数据"""
        agents_data = [
            {"id": agent_id, "status": "active"}
            for agent_id in state.agents
        ]
        
        behaviors_data = [
            b.to_dict()
            for b in state.behaviors
        ]
        
        connections = []
        for i, agent1 in enumerate(state.agents):
            for agent2 in state.agents[i+1:]:
                connections.append({
                    "source": agent1,
                    "target": agent2,
                    "strength": 0.5,
                })
        
        metrics = {
            "agent_count": len(state.agents),
            "behavior_count": len(state.behaviors),
            "version": state.version,
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
            lines.append(f"    {agent_id}")
        
        for i, agent1 in enumerate(state.agents):
            for agent2 in state.agents[i+1:]:
                lines.append(f"    {agent1} --> {agent2}")
        
        return "\n".join(lines)
