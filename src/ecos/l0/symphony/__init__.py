"""Symphony Protocol -- stage-gate orchestration primitives.

Includes: stage machine, agent matcher, trigger engine, and data models.
"""

from .matcher import AgentMatcher
from .models import (
    AgentCapability,
    AgentProfile,
    MatchResult,
    StageHistoryEntry,
    StageInvariant,
    StageOutput,
    StageTransition,
    SymphonyStage,
    TaskRequirement,
    TransitionCondition,
    TransitionResult,
    Trigger,
    TriggerResult,
    TriggerType,
)
from .state_machine import SymphonyStateMachine
from .triggers import TriggerEngine, create_default_triggers, setup_trigger_engine

__all__ = (
    "AgentCapability",
    "AgentMatcher",
    "AgentProfile",
    "MatchResult",
    "StageHistoryEntry",
    "StageInvariant",
    "StageOutput",
    "StageTransition",
    "SymphonyStage",
    "SymphonyStateMachine",
    "TaskRequirement",
    "TransitionCondition",
    "TransitionResult",
    "Trigger",
    "TriggerEngine",
    "TriggerResult",
    "TriggerType",
    "create_default_triggers",
    "setup_trigger_engine",
)
