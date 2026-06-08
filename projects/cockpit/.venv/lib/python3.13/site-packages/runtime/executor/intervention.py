"""Intervention executor — human oversight for anomaly-driven interventions.

Migrated from agentmesh intervention-executor.ts.

Supports pause, rollback, scale, and alert interventions with
optional human confirmation workflow.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class InterventionAction(StrEnum):
    PAUSE = "pause"
    ROLLBACK = "rollback"
    SCALE = "scale"
    ALERT = "alert"
    IGNORE = "ignore"


@dataclass
class InterventionResult:
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str = ""
    action: InterventionAction = InterventionAction.IGNORE
    success: bool = False
    required_confirmation: bool = False
    confirmed: bool = False
    message: str = ""
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


ConfirmationCallback = Callable[[str, InterventionAction, str, dict], bool]


@dataclass
class OperationCallbacks:
    pause: Callable[[str, str], bool] | None = None
    rollback: Callable[[str, str], bool] | None = None
    scale: Callable[[str, float, str], bool] | None = None
    alert: Callable[[str, str, str, dict], None] | None = None


@dataclass
class ExecutorConfig:
    auto_intervention_enabled: bool = False
    default_require_confirmation: bool = True
    confirmation_timeout_ms: float = 30_000.0
    max_retries: int = 3
    retry_delay_ms: float = 1000.0
    record_history: bool = True
    max_history_size: int = 1000


class InterventionExecutor:
    """Execute intervention actions with optional human confirmation."""

    def __init__(
        self,
        callbacks: OperationCallbacks,
        config: ExecutorConfig | None = None,
    ) -> None:
        self._config = config or ExecutorConfig()
        self._callbacks = callbacks
        self._confirmation_callbacks: dict[str, ConfirmationCallback] = {}
        self._history: list[InterventionResult] = []

    async def execute(
        self,
        project_id: str,
        action: InterventionAction,
        reason: str,
        details: dict | None = None,
    ) -> InterventionResult:
        start = time.monotonic()
        exec_id = uuid.uuid4().hex[:12]
        details = details or {}
        needs_confirm = self._requires_confirmation(action)
        confirmed = not needs_confirm
        if needs_confirm:
            confirmed = self._request_confirmation(project_id, action, reason, details)
            if not confirmed:
                return self._make_result(
                    exec_id, project_id, action, False, needs_confirm, False,
                    "Intervention denied by user", start,
                )
        success = False
        message = ""
        error: str | None = None
        try:
            if action == InterventionAction.PAUSE:
                success, message = await self._do_pause(project_id, reason)
            elif action == InterventionAction.ROLLBACK:
                success, message = await self._do_rollback(project_id, reason)
            elif action == InterventionAction.SCALE:
                success, message = await self._do_scale(project_id, reason)
            elif action == InterventionAction.ALERT:
                success, message = await self._do_alert(project_id, reason, details)
            elif action == InterventionAction.IGNORE:
                success = True
                message = "Anomaly ignored"
        except Exception as exc:
            error = str(exc)
            message = f"Execution failed: {error}"
            success = False
        return self._make_result(exec_id, project_id, action, success, needs_confirm, confirmed, message, start, error)

    # -- Internal action methods ------------------------------------------

    async def _do_pause(self, project_id: str, reason: str) -> tuple[bool, str]:
        if self._callbacks.pause:
            ok = await _maybe_async(self._callbacks.pause, project_id, reason)
            return ok, "Project paused" if ok else "Pause failed"
        return False, "Pause callback not configured"

    async def _do_rollback(self, project_id: str, reason: str) -> tuple[bool, str]:
        if self._callbacks.rollback:
            ok = await _maybe_async(self._callbacks.rollback, project_id, reason)
            return ok, "Project rolled back" if ok else "Rollback failed"
        return False, "Rollback callback not configured"

    async def _do_scale(self, project_id: str, reason: str) -> tuple[bool, str]:
        if self._callbacks.scale:
            ok = await _maybe_async(self._callbacks.scale, project_id, 0.5, reason)
            return ok, "Resources scaled down 50%" if ok else "Scale failed"
        return False, "Scale callback not configured"

    async def _do_alert(self, project_id: str, reason: str, details: dict) -> tuple[bool, str]:
        if self._callbacks.alert:
            severity = details.get("severity", "warning")
            await _maybe_async(self._callbacks.alert, project_id, severity, reason, details)
            return True, "Alert sent"
        return True, "Alert recorded (no callback)"

    # -- Confirmation -----------------------------------------------------

    def _requires_confirmation(self, action: InterventionAction) -> bool:
        if not self._config.auto_intervention_enabled:
            return True
        if self._config.default_require_confirmation:
            return True
        if action in (InterventionAction.PAUSE, InterventionAction.ROLLBACK):
            return True
        return False

    def _request_confirmation(
        self,
        project_id: str,
        action: InterventionAction,
        reason: str,
        details: dict,
    ) -> bool:
        key = f"{project_id}_{action.value}"
        cb = self._confirmation_callbacks.get(key) or self._confirmation_callbacks.get("*")
        if cb:
            return cb(project_id, action, reason, details)
        return False

    def register_confirmation_callback(self, key: str, callback: ConfirmationCallback) -> None:
        self._confirmation_callbacks[key] = callback

    # -- History ----------------------------------------------------------

    def _make_result(
        self, exec_id: str, project_id: str, action: InterventionAction,
        success: bool, needs_confirm: bool, confirmed: bool,
        message: str, start: float, error: str | None = None,
    ) -> InterventionResult:
        result = InterventionResult(
            execution_id=exec_id, project_id=project_id, action=action,
            success=success, required_confirmation=needs_confirm,
            confirmed=confirmed, message=message, error=error,
            timestamp=time.time(), duration_ms=(time.monotonic() - start) * 1000,
        )
        if self._config.record_history:
            self._history.append(result)
            while len(self._history) > self._config.max_history_size:
                self._history.pop(0)
        return result

    def get_history(self, project_id: str | None = None, limit: int | None = None) -> list[InterventionResult]:
        history = list(self._history)
        if project_id:
            history = [r for r in history if r.project_id == project_id]
        history.reverse()
        if limit is not None:
            history = history[:limit]
        return history

    def clear_history(self) -> None:
        self._history.clear()

    def get_stats(self) -> dict:
        total = len(self._history)
        successful = sum(1 for r in self._history if r.success)
        by_action: dict[str, int] = {}
        total_duration = 0.0
        for r in self._history:
            by_action[r.action.value] = by_action.get(r.action.value, 0) + 1
            total_duration += r.duration_ms
        confirmed = sum(1 for r in self._history if r.required_confirmation and r.confirmed)
        needed = sum(1 for r in self._history if r.required_confirmation)
        return {
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": total - successful,
            "by_action": by_action,
            "confirmation_rate": confirmed / needed if needed > 0 else 1.0,
            "avg_duration_ms": total_duration / total if total > 0 else 0.0,
        }


async def _maybe_async(fn: Any, *args: Any, **kwargs: Any) -> Any:
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result
