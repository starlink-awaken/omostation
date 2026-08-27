from __future__ import annotations

from ._compat import GovernanceAction, GovernanceState, WorkerHandle, WorkerState

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Governance ≡ Module
# 内涵 ≝ {Governance}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Governance)}
# 功能 ⊢ {Init_Governance, Execute_Governance, Validate_Governance}
# =============================================================================

"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: SwarmGovernance — runtime governance action application for swarm workers.
  Extracted from SwarmLifecycleManager.apply_governance_action() and helpers.
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md

Responsibility: Single — apply runtime governance actions (DOWNGRADE/RESTORE/FREEZE/RECLAIM)
to live workers. Does NOT handle spawning, reaping, or persistence.
"""

from collections.abc import Callable
from typing import TypedDict

_DEGRADED_RUNTIME_EU_CAP = 0.5


class GovernanceApplyResult(TypedDict):
    worker_id: str
    governance_status: str
    runtime_effect: str
    last_action: str
    last_reason: str


class SwarmGovernance:
    """
    Apply runtime governance actions to live swarm workers.

    Responsibility: Single — translate GovernanceAction enum values into
    runtime effects (state transitions, EU budget changes, reaping).
    """

    def __init__(
        self,
        *,
        reap_fn: Callable[[str, str], object],  # SwarmLifecycleManager.reap_by_id
        transition_fn: Callable[[str, WorkerState], None],  # SwarmLifecycleManager.update_state
        governance_state_from_handle: Callable[[WorkerHandle], GovernanceState],
        governance_project_onto_handle: Callable[[WorkerHandle, GovernanceState], None],
        events_emit: Callable[[str, dict[str, str]], None],  # SwarmEventEmitter.emit
    ) -> None:
        self._reap = reap_fn
        self._transition = transition_fn
        self._gs_from_handle = governance_state_from_handle
        self._gs_project = governance_project_onto_handle
        self._emit = events_emit

    def apply(
        self,
        worker_id: str,
        handle: WorkerHandle,
        action: str,
        actor_id: str,
        reason: str,
    ) -> GovernanceApplyResult:
        """Apply a governance action to a worker and return the result."""

        normalized_action = GovernanceAction(str(action).upper())

        governance_state = self._gs_from_handle(handle)
        event = governance_state.apply_action(
            normalized_action,
            actor_id=actor_id,
            reason=reason,
        )
        self._gs_project(handle, governance_state)

        runtime_effect = "status_only"
        if normalized_action is GovernanceAction.DOWNGRADE:
            handle.eu_budget = min(handle.eu_budget, _DEGRADED_RUNTIME_EU_CAP)
            # DOWNGRADE → STARVING if currently ACTIVE
            if handle.state == WorkerState.ACTIVE:
                self._transition(worker_id, WorkerState.STARVING)
            runtime_effect = "budget_capped"
        elif normalized_action is GovernanceAction.RESTORE:
            if handle.state == WorkerState.STARVING:
                self._transition(worker_id, WorkerState.ACTIVE)
            runtime_effect = "restored"
        elif normalized_action in (GovernanceAction.FREEZE, GovernanceAction.RECLAIM):
            runtime_effect = "reaped"
            self._reap(
                worker_id,
                f"governance:{normalized_action.value.lower()}:{reason}",
            )

        self._emit(
            "worker.governance.updated",
            {
                "worker_id": worker_id,
                "action": normalized_action.value,
                "status": governance_state.status.value,
                "runtime_effect": runtime_effect,
            },
        )
        return {
            "worker_id": worker_id,
            "governance_status": governance_state.status.value,
            "runtime_effect": runtime_effect,
            "last_action": event.action.value,
            "last_reason": event.reason,
        }
