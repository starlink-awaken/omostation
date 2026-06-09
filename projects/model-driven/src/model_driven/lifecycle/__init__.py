"""
model_driven.lifecycle — 全生命周期引擎

提供 7 阶段生命周期管理的完整能力：
- 阶段定义与状态机
- 门禁检查引擎
- 阶段转换规则
- 全生命周期追踪
"""

from .gates import CheckResult, GateEngine, GateExecution, GateResult
from .stages import LifecycleTracker, StageInstance, StageStatus
from .tracking import LifecycleDashboard, LifecycleManager
from .transitions import STANDARD_TRANSITIONS, TransitionEngine, TransitionRule

__all__ = [
    # Stages
    "StageStatus",
    "StageInstance",
    "LifecycleTracker",
    # Gates
    "GateResult",
    "CheckResult",
    "GateExecution",
    "GateEngine",
    # Transitions
    "TransitionRule",
    "TransitionEngine",
    "STANDARD_TRANSITIONS",
    # Tracking
    "LifecycleManager",
    "LifecycleDashboard",
]
