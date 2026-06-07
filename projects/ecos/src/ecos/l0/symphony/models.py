"""Symphony protocol data models — stage-gate orchestration primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SymphonyStage(StrEnum):
    ANCHORING = "anchoring"
    SCAFFOLDING = "scaffolding"
    IMPLEMENTATION = "implementation"
    POLISHING = "polishing"
    COMPLETE = "complete"


class TriggerType(StrEnum):
    CONDITION_MET = "condition_met"
    TIMER = "timer"
    MANUAL = "manual"
    STAGE_ENTER = "stage_enter"
    STAGE_EXIT = "stage_exit"


# -- Stage Transition --


@dataclass
class TransitionCondition:
    name: str
    predicate: Callable[[dict[str, Any]], bool]
    threshold: float = 1.0
    description: str = ""


@dataclass
class TransitionResult:
    success: bool
    from_stage: SymphonyStage | None
    to_stage: SymphonyStage
    conditions_met: list[str] = field(default_factory=list)
    conditions_failed: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class StageTransition:
    from_stage: SymphonyStage
    to_stage: SymphonyStage

    def is_valid(self) -> bool:
        transitions = {
            SymphonyStage.ANCHORING: [SymphonyStage.SCAFFOLDING],
            SymphonyStage.SCAFFOLDING: [SymphonyStage.IMPLEMENTATION],
            SymphonyStage.IMPLEMENTATION: [SymphonyStage.POLISHING],
            SymphonyStage.POLISHING: [SymphonyStage.COMPLETE],
            SymphonyStage.COMPLETE: [],
        }
        return self.to_stage in transitions.get(self.from_stage, [])


@dataclass
class StageHistoryEntry:
    stage: SymphonyStage
    entered_at: datetime = field(default_factory=datetime.now)
    exited_at: datetime | None = None
    output: StageOutput | None = None


# -- Stage Invariants & Outputs --


@dataclass
class StageInvariant:
    name: str
    predicate: Callable[[dict[str, Any]], bool] = field(default=lambda ctx: True)
    violation_action: str = "WARN"
    condition: str = ""
    severity: str = "error"


@dataclass
class StageOutput:
    stage: SymphonyStage
    artifacts: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


# -- Agent Matching --


@dataclass(frozen=True)
class AgentCapability:
    name: str
    proficiency: float = 0.8
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class AgentProfile:
    agent_id: str
    capabilities: dict[AgentCapability, float] = field(default_factory=dict)
    historical_performance: dict[str, float] = field(default_factory=dict)
    current_load: float = 0.0
    specialization: str | None = None
    max_capacity: int = 10


@dataclass
class TaskRequirement:
    task_id: str
    required_capabilities: set[AgentCapability] = field(default_factory=set)
    complexity: int = 5
    priority: int = 5


@dataclass
class MatchResult:
    task_id: str
    agent_id: str
    score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""


# -- Triggers --


@dataclass
class Trigger:
    id: str
    name: str
    trigger_type: TriggerType = TriggerType.CONDITION_MET
    condition: Callable[[dict[str, Any]], bool] = field(default=lambda ctx: True)
    action: Callable[[], Any] = field(default=lambda: None)
    priority: int = 50
    enabled: bool = True


@dataclass
class TriggerResult:
    trigger_id: str
    triggered: bool
    action_result: Any = None
    message: str = ""
