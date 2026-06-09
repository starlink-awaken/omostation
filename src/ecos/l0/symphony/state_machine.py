"""Symphony Protocol state machine — stage transition validation and execution.

Adapted from SharedBrain D_Execution symphony/state_machine.py.
All CoreService dependencies removed; uses standalone classes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .models import (
    StageHistoryEntry,
    StageInvariant,
    StageOutput,
    SymphonyStage,
    TransitionCondition,
    TransitionResult,
)

logger = logging.getLogger(__name__)


class SymphonyStateMachine:
    """Formal state machine for Symphony Protocol stage transitions.

    Uses a transition matrix to define legal stage transitions
    and formal verification to ensure transition correctness.
    """

    TRANSITION_MATRIX: dict[
        tuple[SymphonyStage | None, SymphonyStage], list[TransitionCondition]
    ] = {
        (None, SymphonyStage.ANCHORING): [
            TransitionCondition(
                name="task_defined",
                predicate=lambda ctx: ctx.get("task") is not None,
                threshold=1.0,
                description="task defined",
            )
        ],
        (SymphonyStage.ANCHORING, SymphonyStage.SCAFFOLDING): [
            TransitionCondition(
                name="context_completeness",
                predicate=lambda ctx: ctx.get("context_completeness", 0) >= 0.95,
                threshold=0.95,
                description="context completeness >= 95%",
            ),
            TransitionCondition(
                name="ambiguity_resolved",
                predicate=lambda ctx: len(ctx.get("ambiguities", [])) == 0,
                threshold=1.0,
                description="all ambiguities resolved",
            ),
            TransitionCondition(
                name="truth_locked",
                predicate=lambda ctx: ctx.get("truth_locked", False) is True,
                threshold=1.0,
                description="baseline truth locked",
            ),
        ],
        (SymphonyStage.SCAFFOLDING, SymphonyStage.IMPLEMENTATION): [
            TransitionCondition(
                name="architecture_defined",
                predicate=lambda ctx: ctx.get("architecture") is not None,
                threshold=1.0,
                description="architecture defined",
            ),
            TransitionCondition(
                name="contract_signed",
                predicate=lambda ctx: ctx.get("contract_signed", False) is True,
                threshold=1.0,
                description="interface contract signed",
            ),
            TransitionCondition(
                name="dependency_graph_built",
                predicate=lambda ctx: ctx.get("dependency_graph") is not None,
                threshold=1.0,
                description="dependency graph built",
            ),
        ],
        (SymphonyStage.IMPLEMENTATION, SymphonyStage.POLISHING): [
            TransitionCondition(
                name="code_complete",
                predicate=lambda ctx: ctx.get("code_completion_rate", 0) >= 0.95,
                threshold=0.95,
                description="code completion >= 95%",
            ),
            TransitionCondition(
                name="code_coverage",
                predicate=lambda ctx: ctx.get("code_coverage", 0) >= 0.80,
                threshold=0.80,
                description="test coverage >= 80%",
            ),
            TransitionCondition(
                name="no_critical_issues",
                predicate=lambda ctx: ctx.get("critical_issues", 0) == 0,
                threshold=1.0,
                description="no critical issues",
            ),
        ],
        (SymphonyStage.POLISHING, SymphonyStage.COMPLETE): [
            TransitionCondition(
                name="all_tests_passed",
                predicate=lambda ctx: ctx.get("tests_passed", False) is True,
                threshold=1.0,
                description="all tests passed",
            ),
            TransitionCondition(
                name="performance_benchmark",
                predicate=lambda ctx: ctx.get("performance_score", 0) >= 0.90,
                threshold=0.90,
                description="performance benchmark met",
            ),
            TransitionCondition(
                name="self_review_passed",
                predicate=lambda ctx: ctx.get("self_review_score", 0) >= 0.85,
                threshold=0.85,
                description="self-review passed",
            ),
        ],
    }

    STAGE_INVARIANTS: dict[SymphonyStage, list[StageInvariant]] = {
        SymphonyStage.ANCHORING: [
            StageInvariant(
                name="context_immutable",
                predicate=lambda ctx: ctx.get("context_frozen", False) is True,
                violation_action="ABORT",
            ),
            StageInvariant(
                name="truth_consistent",
                predicate=lambda ctx: not ctx.get("truth_contradiction", False),
                violation_action="ABORT",
            ),
        ],
        SymphonyStage.SCAFFOLDING: [
            StageInvariant(
                name="architecture_layered",
                predicate=lambda ctx: ctx.get("architecture_layers", 0) >= 3,
                violation_action="WARN",
            )
        ],
        SymphonyStage.IMPLEMENTATION: [
            StageInvariant(
                name="agent_isolation",
                predicate=lambda ctx: not ctx.get("agent_conflict", False),
                violation_action="ABORT",
            )
        ],
        SymphonyStage.POLISHING: [
            StageInvariant(
                name="test_coverage_maintained",
                predicate=lambda ctx: ctx.get("code_coverage", 0) >= 0.75,
                violation_action="WARN",
            )
        ],
    }

    def __init__(self, initial_context: dict[str, Any] | None = None) -> None:
        self._current_stage: SymphonyStage | None = None
        self._history: list[TransitionResult] = []
        self._stage_history: list[StageHistoryEntry] = []
        self._context: dict[str, Any] = initial_context or {}
        self._current_stage_entry: StageHistoryEntry | None = None

    def can_transition(self, to_stage: SymphonyStage) -> bool:
        transition_key = (self._current_stage, to_stage)
        if transition_key not in self.TRANSITION_MATRIX:
            return False
        conditions = self.TRANSITION_MATRIX[transition_key]
        return all(condition.predicate(self._context) for condition in conditions)

    def transition(self, to_stage: SymphonyStage) -> TransitionResult:
        transition_key = (self._current_stage, to_stage)
        if transition_key not in self.TRANSITION_MATRIX:
            return TransitionResult(
                success=False,
                from_stage=self._current_stage,
                to_stage=to_stage,
                message=f"illegal transition: {self._current_stage} -> {to_stage}",
            )

        conditions = self.TRANSITION_MATRIX[transition_key]
        conditions_met: list[str] = []
        conditions_failed: list[str] = []

        for condition in conditions:
            if condition.predicate(self._context):
                conditions_met.append(condition.name)
            else:
                conditions_failed.append(condition.name)

        if conditions_failed:
            return TransitionResult(
                success=False,
                from_stage=self._current_stage,
                to_stage=to_stage,
                conditions_met=conditions_met,
                conditions_failed=conditions_failed,
                message=f"conditions not met: {conditions_failed}",
            )

        from_stage = self._current_stage
        if self._current_stage_entry:
            self._current_stage_entry.exited_at = datetime.now()
            self._stage_history.append(self._current_stage_entry)

        self._current_stage = to_stage
        self._current_stage_entry = StageHistoryEntry(stage=to_stage)

        result = TransitionResult(
            success=True,
            from_stage=from_stage,
            to_stage=to_stage,
            conditions_met=conditions_met,
            message=f"transitioned to {to_stage.name}",
        )

        self._history.append(result)
        logger.info("Symphony transition: %s -> %s", from_stage, to_stage)

        # 强制将关键状态机跃迁写入 L0 SSB Immutable Log (X3 锚定)
        try:
            import httpx

            httpx.post(
                "http://127.0.0.1:8080/v1/tools/call",
                json={
                    "name": "append_ssb_log",
                    "arguments": {
                        "event_type": "SYMPHONY_TRANSITION",
                        "agent_name": "protocols_layer.symphony",
                        "summary": f"State Machine transitioned to {to_stage.name}",
                        "detail": f"From {from_stage.name if from_stage else 'None'} -> {to_stage.name}. Conditions met: {conditions_met}",
                    },
                },
                timeout=0.5,
            )
        except Exception:
            pass  # Do not block state machine on logging failure

        return result

    def get_current_stage(self) -> SymphonyStage | None:
        return self._current_stage

    def get_history(self) -> list[TransitionResult]:
        return self._history.copy()

    def get_stage_history(self) -> list[StageHistoryEntry]:
        return self._stage_history.copy()

    def validate_invariants(self) -> list[str]:
        if self._current_stage is None:
            return []
        invariants = self.STAGE_INVARIANTS.get(self._current_stage, [])
        violated = []
        for invariant in invariants:
            if not invariant.predicate(self._context):
                violated.append(invariant.name)
                logger.warning("invariant violation: %s", invariant.name)
        return violated

    def update_context(self, updates: dict[str, Any]) -> None:
        self._context.update(updates)

    def get_context(self) -> dict[str, Any]:
        return self._context.copy()

    def set_stage_output(self, output: StageOutput) -> None:
        if self._current_stage_entry:
            self._current_stage_entry.output = output

    def get_valid_transitions(self) -> list[SymphonyStage]:
        if self._current_stage is None:
            return [SymphonyStage.ANCHORING]
        valid_targets = []
        for from_stage, to_stage in self.TRANSITION_MATRIX:
            if from_stage == self._current_stage:
                valid_targets.append(to_stage)
        return valid_targets

    def is_complete(self) -> bool:
        return self._current_stage == SymphonyStage.COMPLETE

    def reset(self, initial_context: dict[str, Any] | None = None) -> None:
        self._current_stage = None
        self._history = []
        self._stage_history = []
        self._context = initial_context or {}
        self._current_stage_entry = None
        logger.info("state machine reset")
