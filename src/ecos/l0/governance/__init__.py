"""L0 治理模块 — X1-X4 治理框架 + 蜂群式AI超级大脑原语

M1 SSOT: ecos/ssot/mof/m1/governance/
M2 Schema: ecos/ssot/mof/m2/governance_*.yaml
注册表: .omo/_truth/registry/governance-checks.yaml

本模块实现:
1. X1-X4 治理框架原语 (5 个检查器)
2. 优化原语 (告警/仪表板/历史)
3. 蜂群式AI超级大脑原语:
   - 分布式原语: CRDTSync + StateSyncService + NodeManager + CommunicationProtocol
   - 角色原语: RoleManager + RoleCollaboration + RoleSwitcher + RoleEvaluator
   - 蜂群原语: SwarmManager + EmergenceDetector + CollectiveDecision + SwarmVisualizer
   - 个人知识原语: PersonalKnowledgeManager + KnowledgeGraphBuilder + PreferenceEngine + RecommendationEngine
   - 任务调度: TaskScheduler + DAGScheduler
   - 故障转移: FailoverManager
   - 负载均衡: LoadBalancer
   - Agent注册: AgentRegistry

L1/L2/L3 层全部委托本模块原语。
"""

from .agent_registry import AgentInfo, AgentRegistry, AgentStatus
from .alert_engine import AlertEngine, LogHandler, WebhookHandler
from .checkers import (
    SwarmBrainStructureChecker,
    X1AuditChainChecker,
    X2StalenessChecker,
    X3ValueChecker,
    X4ConsistencyChecker,
)
from .distributed import (
    CommunicationProtocol,
    CRDTSync,
    DistributedPrimitive,
    Message,
    MessageType,
    NodeInfo,
    NodeManager,
    NodeStatus,
    ProtocolType,
    StateSnapshot,
    StateSyncService,
    SyncResult,
    SyncStrategy,
)
from .event_bus import GovernanceEventBus
from .failover import FailoverManager, FailoverRule, FailoverStrategy
from .history_store import SQLiteHistoryStore
from .load_balancer import LoadBalancer, LoadBalancingStrategy, NodeLoad
from .optimization import (
    AlertChannel,
    AlertHandler,
    AlertRule,
    AlertSeverity,
    DashboardData,
    DashboardMetric,
    DashboardProvider,
    GovernanceAlert,
    HealthSnapshot,
    HistoryAnalyzer,
    Prediction,
    TrendAnalysis,
)
from .personal import (
    GraphEdge,
    KnowledgeGraphBuilder,
    KnowledgeNode,
    KnowledgeType,
    PersonalKnowledgeManager,
    PersonalKnowledgePrimitive,
    PreferenceEngine,
    PreferenceType,
    Recommendation,
    RecommendationEngine,
    UserPreference,
)
from .primitives import (
    CheckResult,
    CheckSeverity,
    CheckStatus,
    GovernanceCheck,
    GovernanceEvent,
)
from .registry import CheckerRegistration, GovernanceRegistry
from .role import (
    AgentRole,
    CollaborationMode,
    CollaborationTask,
    RoleCollaboration,
    RoleDefinition,
    RoleEvaluation,
    RoleEvaluator,
    RoleManager,
    RolePrimitive,
    RoleStatus,
    RoleSwitcher,
    RoleType,
)
from .swarm import (
    CollectiveDecision,
    DecisionMethod,
    DecisionProposal,
    EmergenceDetector,
    EmergenceLevel,
    EmergencePattern,
    EmergentBehavior,
    SwarmManager,
    SwarmPrimitive,
    SwarmState,
    SwarmVisualization,
    SwarmVisualizer,
)
from .task_scheduler import DAGScheduler, TaskInfo, TaskScheduler, TaskStatus

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
    "SwarmBrainStructureChecker",
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
    "ProtocolType",
    "MessageType",
    "Message",
    "StateSnapshot",
    "SyncResult",
    "DistributedPrimitive",
    "CRDTSync",
    "NodeManager",
    "NodeInfo",
    "StateSyncService",
    "CommunicationProtocol",
    # Agent 注册中心
    "AgentRegistry",
    "AgentInfo",
    "AgentStatus",
    # 任务调度
    "TaskScheduler",
    "TaskInfo",
    "TaskStatus",
    "DAGScheduler",
    # 故障转移
    "FailoverManager",
    "FailoverRule",
    "FailoverStrategy",
    # 负载均衡
    "LoadBalancer",
    "LoadBalancingStrategy",
    "NodeLoad",
    # 角色原语
    "RoleType",
    "RoleStatus",
    "CollaborationMode",
    "RoleDefinition",
    "AgentRole",
    "CollaborationTask",
    "RoleEvaluation",
    "RolePrimitive",
    "RoleManager",
    "RoleCollaboration",
    "RoleEvaluator",
    "RoleSwitcher",
    # 蜂群原语
    "EmergencePattern",
    "EmergenceLevel",
    "DecisionMethod",
    "EmergentBehavior",
    "SwarmState",
    "DecisionProposal",
    "SwarmVisualization",
    "SwarmPrimitive",
    "SwarmManager",
    "EmergenceDetector",
    "CollectiveDecision",
    "SwarmVisualizer",
    # 个人知识原语
    "KnowledgeType",
    "PreferenceType",
    "KnowledgeNode",
    "UserPreference",
    "GraphEdge",
    "Recommendation",
    "PersonalKnowledgePrimitive",
    "PersonalKnowledgeManager",
    "KnowledgeGraphBuilder",
    "PreferenceEngine",
    "RecommendationEngine",
]
