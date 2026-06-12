"""L0 治理原语 — X1-X4 治理框架核心数据结构

M1 SSOT: .omo/_knowledge/governance/x1-x4-architecture.md
M2 Schema: ecos/ssot/mof/m2/governance_check.yaml
M2 Schema: ecos/ssot/mof/m2/governance_event.yaml
M2 Schema: ecos/ssot/mof/m2/governance_policy.yaml

本模块实现 M1 定义的 X1-X4 治理框架原语。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class CheckSeverity(Enum):
    """检查严重程度
    
    M2 Schema: governance_check.yaml > properties > severity
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CheckStatus(Enum):
    """检查状态
    
    M2 Schema: governance_check.yaml > stateMachine
    """
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class CheckResult:
    """检查结果
    
    M2 Schema: governance_check.yaml
    M1 定义: X1-X4 检查器输出标准格式
    """
    check_id: str
    dimension: str  # X1/X2/X3/X4
    status: CheckStatus
    message: str
    severity: CheckSeverity = CheckSeverity.MEDIUM
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典 — 符合 M2 Schema"""
        return {
            "check_id": self.check_id,
            "dimension": self.dimension,
            "status": self.status.value,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class GovernanceEvent:
    """治理事件
    
    M2 Schema: governance_event.yaml
    M1 定义: 事件流标准格式
    """
    event_type: str  # check_started / check_completed / alert_triggered
    dimension: str
    check_id: str
    result: Optional[CheckResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典 — 符合 M2 Schema"""
        return {
            "event_type": self.event_type,
            "dimension": self.dimension,
            "check_id": self.check_id,
            "result": self.result.to_dict() if self.result else None,
            "timestamp": self.timestamp.isoformat(),
        }


class GovernanceCheck(ABC):
    """治理检查器基类
    
    M1 SSOT: ecos/ssot/mof/m1/governance/GOV-X1-CONSTRAINT.yaml
    M1 SSOT: ecos/ssot/mof/m1/governance/GOV-X2-POLICY.yaml
    M1 SSOT: ecos/ssot/mof/m1/governance/GOV-X3-VALUE.yaml
    M1 SSOT: ecos/ssot/mof/m1/governance/GOV-X4-CONSISTENCY.yaml
    
    所有 X1-X4 检查器必须继承此基类。
    """
    
    def __init__(self, check_id: str, dimension: str):
        self.check_id = check_id
        self.dimension = dimension
    
    @abstractmethod
    def execute(self) -> CheckResult:
        """执行检查"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取检查描述"""
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.check_id} dim={self.dimension}>"
