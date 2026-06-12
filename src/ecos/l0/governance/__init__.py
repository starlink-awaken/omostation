"""L0 治理模块 — X1-X4 治理框架"""

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
]
