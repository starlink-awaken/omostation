from __future__ import annotations

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
# Call Dispatcher ≡ Module
# 内涵 ≝ {Call, Dispatcher}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CallDispatcher)}
# 功能 ⊢ {Call_Dispatcher, Init_Call, Validate_Dispatcher}
# =============================================================================

"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: CallDispatcher — CoreService.call() action handlers for SwarmLifecycleManager.
  Extracted from SwarmLifecycleManager._handle_spawn/reap/update_state/governance_action/list_active().
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md

Responsibility: Single — handle CoreService.call() action dispatch.
This is infrastructure plumbing, not domain logic.
"""

import logging
import math
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

if TYPE_CHECKING:
    from nucleus.Z_Spore.interfaces.swarm import (  # type: ignore[import]
        GovernanceAction,
        WorkerBundle,
        WorkerHandle,
        WorkerState,
    )

_log = logging.getLogger(__name__)


class GovernanceActionResult(TypedDict):
    worker_id: str
    governance_status: str
    runtime_effect: str
    last_action: str
    last_reason: str


class LifecycleManagerProtocol(Protocol):
    def spawn(
        self,
        capability: str,
        eu_budget: float,
        task_prompt: str,
        *,
        cost_class: Any = ...,
    ) -> WorkerHandle: ...

    def reap_by_id(self, worker_id: str, reason: str = ...) -> WorkerBundle: ...

    def update_state(self, worker_id: str, new_state: WorkerState) -> None: ...

    def apply_governance_action(
        self,
        worker_id: str,
        *,
        action: str,
        actor_id: str,
        reason: str,
    ) -> GovernanceActionResult: ...

    def list_active(self) -> list[WorkerHandle]: ...


class CallDispatcher:
    """
    Handles CoreService.call() action dispatch for swarm lifecycle.

    Responsibility: Single — translate action strings + param dicts into
    SwarmLifecycleManager method calls and return serialisable result dicts.
    """

    def __init__(
        self,
        manager: LifecycleManagerProtocol,  # SwarmLifecycleManager instance
    ) -> None:
        self._manager = manager

    def dispatch(
        self,
        action: str,
        params: dict[str, object] | None,
    ) -> dict[str, object]:
        """Dispatch an action string to the appropriate handler method."""
        if params is None:
            normalized_params: dict[str, object] = {}
        elif isinstance(params, dict):
            normalized_params = params
        else:
            return {"status": "error", "message": "Invalid params"}
        handler_name = f"_handle_{action}"
        handler = getattr(self, handler_name, None)
        if handler is not None:
            return handler(normalized_params)
        return {
            "status": "error",
            "message": f"Action '{action}' not implemented",
        }

    @staticmethod
    def _required_non_empty_string(
        params: dict[str, object],
        key: str,
    ) -> str | None:
        value = params.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        return None

    # ─── Action handlers ───────────────────────────────────────────────────────

    def _handle_spawn(self, params: dict[str, object]) -> dict[str, object]:
        capability = self._required_non_empty_string(params, "capability")
        if capability is None:
            return {"status": "error", "message": "Invalid capability"}
        task_prompt = self._required_non_empty_string(params, "task_prompt")
        if task_prompt is None:
            return {"status": "error", "message": "Invalid task_prompt"}
        eu_budget_value = params.get("eu_budget", 0)
        if isinstance(eu_budget_value, bool):
            return {"status": "error", "message": "Invalid eu_budget"}
        if isinstance(eu_budget_value, (int, float)):
            eu_budget = float(eu_budget_value)
        elif isinstance(eu_budget_value, str):
            try:
                eu_budget = float(eu_budget_value)
            except ValueError:
                return {"status": "error", "message": "Invalid eu_budget"}
        else:
            return {"status": "error", "message": "Invalid eu_budget"}
        if not math.isfinite(eu_budget) or eu_budget <= 0:
            return {"status": "error", "message": "Invalid eu_budget"}
        cost_class = params.get("cost_class")
        handle = self._manager.spawn(capability, eu_budget, task_prompt, cost_class=cost_class)
        return {
            "status": "ok",
            "worker_id": handle.worker_id,
            "pid": handle.pid,
            "state": handle.state.value,
        }

    def _handle_reap(self, params: dict[str, object]) -> dict[str, object]:
        worker_id = self._required_non_empty_string(params, "worker_id")
        if worker_id is None:
            return {"status": "error", "message": "Invalid worker_id"}
        reason_value = params.get("reason", "api_request")
        if not isinstance(reason_value, str):
            return {"status": "error", "message": "Invalid reason"}
        reason = reason_value
        bundle = self._manager.reap_by_id(worker_id, reason=reason)
        return {
            "status": "ok",
            "worker_id": worker_id,
            "total_tasks": bundle.total_tasks,
            "successful_tasks": bundle.successful_tasks,
            "total_eu_consumed": bundle.total_eu_consumed,
        }

    def _handle_update_state(self, params: dict[str, object]) -> dict[str, object]:

        worker_id = self._required_non_empty_string(params, "worker_id")
        if worker_id is None:
            return {"status": "error", "message": "Invalid worker_id"}
        new_state_value = params.get("new_state")
        if not isinstance(new_state_value, str) or not new_state_value:
            return {"status": "error", "message": "Invalid new_state"}
        new_state_str = new_state_value
        try:
            new_state = WorkerState(new_state_str)
        except ValueError:
            return {"status": "error", "message": f"Unknown state: {new_state_str}"}
        self._manager.update_state(worker_id, new_state)
        return {"status": "ok", "worker_id": worker_id, "new_state": new_state_str}

    def _handle_governance_action(self, params: dict[str, object]) -> dict[str, object]:
        worker_id = self._required_non_empty_string(params, "worker_id")
        if worker_id is None:
            return {"status": "error", "message": "Invalid worker_id"}
        action = self._required_non_empty_string(params, "action")
        if action is None:
            return {"status": "error", "message": "Invalid action"}

        normalized_action = action.upper()
        if normalized_action not in {candidate.value for candidate in GovernanceAction}:
            return {"status": "error", "message": "Invalid action"}
        actor_id = self._required_non_empty_string(params, "actor_id")
        if actor_id is None:
            return {"status": "error", "message": "Invalid actor_id"}
        reason_value = params.get("reason", "")
        if not isinstance(reason_value, str):
            return {"status": "error", "message": "Invalid reason"}
        reason = reason_value
        result = self._manager.apply_governance_action(
            worker_id,
            action=normalized_action,
            actor_id=actor_id,
            reason=reason,
        )
        return {"status": "ok", **result}

    def _handle_list_active(self, params: dict[str, object]) -> dict[str, object]:
        handles = self._manager.list_active()
        return {
            "status": "ok",
            "workers": [
                {
                    "worker_id": h.worker_id,
                    "spore_id": h.spore_id,
                    "state": h.state.value,
                    "pid": h.pid,
                    "eu_remaining": h.eu_remaining,
                }
                for h in handles
            ],
        }
