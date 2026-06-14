"""L0 治理模块 — X1-X4 治理框架 + 优化原语 + 蜂群式AI超级大脑原语

M1 SSOT: ecos/ssot/mof/m1/governance/
M2 Schema: ecos/ssot/mof/m2/governance_*.yaml
注册表: .omo/_truth/registry/governance-checks.yaml

本模块实现:
1. X1-X4 治理框架原语
2. 优化原语 (告警/仪表板/历史)
3. 蜂群式AI超级大脑原语 (分布式/角色/蜂群/个人知识)
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
from .distributed import (
    SyncStrategy,
    NodeStatus,
    StateSnapshot,
    SyncResult,
    DistributedPrimitive,
    CRDTSync,
    NodeManager,
    NodeInfo,
)
from .role import (
    RoleType,
    RoleStatus,
    RoleDefinition,
    AgentRole,
    RolePrimitive,
    RoleManager,
)
from .swarm import (
    EmergencePattern,
    EmergenceLevel,
    EmergentBehavior,
    SwarmState,
    SwarmPrimitive,
    SwarmManager,
)
from .personal import (
    KnowledgeType,
    PreferenceType,
    KnowledgeNode,
    UserPreference,
    PersonalKnowledgePrimitive,
    PersonalKnowledgeManager,
)

__all__ = [
    # X1-X4 治理原语
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
    # 分布式原语
    "SyncStrategy",
    "NodeStatus",
    "StateSnapshot",
    "SyncResult",
    "DistributedPrimitive",
    "CRDTSync",
    "NodeManager",
    "NodeInfo",
    # 角色原语
    "RoleType",
    "RoleStatus",
    "RoleDefinition",
    "AgentRole",
    "RolePrimitive",
    "RoleManager",
    # 蜂群原语
    "EmergencePattern",
    "EmergenceLevel",
    "EmergentBehavior",
    "SwarmState",
    "SwarmPrimitive",
    "SwarmManager",
    # 个人知识原语
    "KnowledgeType",
    "PreferenceType",
    "KnowledgeNode",
    "UserPreference",
    "PersonalKnowledgePrimitive",
    "PersonalKnowledgeManager",
]
