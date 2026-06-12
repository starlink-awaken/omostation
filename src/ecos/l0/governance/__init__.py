"""L0 治理模块 — X1-X4 治理框架 + 优化原语

M1 SSOT: ecos/ssot/mof/m1/governance/
M2 Schema: ecos/ssot/mof/m2/governance_*.yaml
注册表: .omo/_truth/registry/governance-checks.yaml
"""

from .primitives import (
    CheckResult,
    CheckSeverity,
    CheckStatus,
    GovernanceCheck,
    GovernanceEvent,
)
from .checkers import (
    X1AuditChainChecker,
    X2StalenessChecker,
    X3ValueChecker,
    X4ConsistencyChecker,
)
from .event_bus import GovernanceEventBus
from .registry import GovernanceRegistry, CheckerRegistration
from .optimization import (
    AlertSeverity,
    AlertChannel,
    GovernanceAlert,
    AlertRule,
    AlertHandler,
    DashboardMetric,
    DashboardData,
    DashboardProvider,
    HealthSnapshot,
    TrendAnalysis,
    Prediction,
    HistoryAnalyzer,
)
from .alert_engine import AlertEngine, LogHandler, WebhookHandler
from .history_store import SQLiteHistoryStore

__all__ = [
    # 原语
    "CheckResult",
    "CheckSeverity",
    "CheckStatus",
    "GovernanceCheck",
    "GovernanceEvent",
    # 检查器
    "X1AuditChainChecker",
    "X2StalenessChecker",
    "X3ValueChecker",
    "X4ConsistencyChecker",
    # 事件总线
    "GovernanceEventBus",
    # 注册表
    "GovernanceRegistry",
    "CheckerRegistration",
    # 优化原语
    "AlertSeverity",
    "AlertChannel",
    "GovernanceAlert",
    "AlertRule",
    "AlertHandler",
    "DashboardMetric",
    "DashboardData",
    "DashboardProvider",
    "HealthSnapshot",
    "TrendAnalysis",
    "Prediction",
    "HistoryAnalyzer",
    # 告警引擎
    "AlertEngine",
    "LogHandler",
    "WebhookHandler",
    # 历史存储
    "SQLiteHistoryStore",
]
