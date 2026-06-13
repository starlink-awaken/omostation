"""L0 蜂群原语 — 为蜂群智能构建基础"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


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


@dataclass
class EmergentBehavior:
    """涌现行为
    
    L0 原语: 蜂群涌现的基本单元
    """
    pattern: EmergencePattern
    agents: list[str]
    confidence: float
    level: EmergenceLevel = EmergenceLevel.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
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


class SwarmPrimitive(ABC):
    """蜂群原语基类
    
    L0 原语: 所有蜂群操作必须继承此基类
    """
    
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
        # 简化实现：检测聚类行为
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
        # 简化实现：预测特化行为
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
        # 简化实现：接受所有控制操作
        return True
    
    def get_swarm_state(self) -> SwarmState:
        """获取蜂群状态"""
        return SwarmState(
            agents=self.agents,
            behaviors=self.behaviors,
            version=self.version,
        )
