"""L0 治理优化原语 — 告警、仪表板、历史分析"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ══════════════════════════════════════════════════════════════
# 告警原语
# ══════════════════════════════════════════════════════════════


class AlertSeverity(Enum):
    """告警严重程度

    对齐: X4 一致性维度
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertChannel(Enum):
    """通知渠道"""

    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"
    MCP = "mcp"


@dataclass
class GovernanceAlert:
    """治理告警

    L0 原语: 所有告警必须符合此结构
    """

    alert_id: str
    severity: AlertSeverity
    dimension: str  # X1/X2/X3/X4
    check_id: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    channels: list[AlertChannel] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "dimension": self.dimension,
            "check_id": self.check_id,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "channels": [c.value for c in self.channels],
        }


@dataclass
class AlertRule:
    """告警规则

    L0 原语: 规则定义
    """

    rule_id: str
    dimension: str
    condition: str
    severity: AlertSeverity
    channels: list[AlertChannel]
    enabled: bool = True


class AlertHandler(ABC):
    """告警处理器基类"""

    @abstractmethod
    def handle(self, alert: GovernanceAlert) -> bool:
        """处理告警，返回是否成功"""
        pass


# ══════════════════════════════════════════════════════════════
# 仪表板原语
# ══════════════════════════════════════════════════════════════


@dataclass
class DashboardMetric:
    """仪表板指标"""

    name: str
    value: float
    unit: str = ""
    trend: str = "stable"  # improving / stable / degrading


@dataclass
class DashboardData:
    """仪表板数据

    L0 原语: 所有仪表板数据必须符合此结构
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    health_score: float = 0.0
    debt_weight: float = 0.0
    debt_health: float = 0.0
    resolved_count: int = 0
    unresolved_count: int = 0
    metrics: list[DashboardMetric] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "health_score": self.health_score,
            "debt_weight": self.debt_weight,
            "debt_health": self.debt_health,
            "resolved_count": self.resolved_count,
            "unresolved_count": self.unresolved_count,
            "metrics": [m.__dict__ for m in self.metrics],
        }


class DashboardProvider(ABC):
    """仪表板数据提供者基类"""

    @abstractmethod
    def get_data(self) -> DashboardData:
        """获取仪表板数据"""
        pass


# ══════════════════════════════════════════════════════════════
# 历史分析原语
# ══════════════════════════════════════════════════════════════


@dataclass
class HealthSnapshot:
    """健康度快照

    L0 原语: 历史数据点
    """

    timestamp: datetime
    health_score: float
    debt_weight: float
    debt_health: float
    resolved_count: int
    unresolved_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "health_score": self.health_score,
            "debt_weight": self.debt_weight,
            "debt_health": self.debt_health,
            "resolved_count": self.resolved_count,
            "unresolved_count": self.unresolved_count,
        }


@dataclass
class TrendAnalysis:
    """趋势分析结果

    L0 原语: 趋势分析输出
    """

    metric: str
    current: float
    previous: float
    change: float
    trend: str  # improving / stable / degrading
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "current": self.current,
            "previous": self.previous,
            "change": self.change,
            "trend": self.trend,
            "confidence": self.confidence,
        }


@dataclass
class Prediction:
    """预测结果

    L0 原语: 预测输出
    """

    metric: str
    days: int
    predicted_value: float
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "days": self.days,
            "predicted_value": self.predicted_value,
            "confidence": self.confidence,
        }


class HistoryAnalyzer(ABC):
    """历史分析器基类"""

    @abstractmethod
    def record(self, snapshot: HealthSnapshot) -> None:
        """记录快照"""
        pass

    @abstractmethod
    def analyze_trend(self, metric: str, days: int = 30) -> TrendAnalysis:
        """分析趋势"""
        pass

    @abstractmethod
    def predict(self, metric: str, days: int = 7) -> list[Prediction]:
        """预测未来"""
        pass
