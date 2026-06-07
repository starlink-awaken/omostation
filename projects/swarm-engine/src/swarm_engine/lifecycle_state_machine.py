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
# State Machine ≡ Module
# 内涵 ≝ {State, Machine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, StateMachine)}
# 功能 ⊢ {State_Machine, Init_State, Validate_Machine}
# =============================================================================

"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: Swarm state machine — validates worker state transitions.
  Extracted from SwarmLifecycleManager._VALID_TRANSITIONS and _transition_state().
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
---

Responsibility: Single — enforce the WorkerState transition rules.
Does not hold worker data; only validates transitions.
"""

import logging
from collections.abc import Callable
from threading import RLock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_log = logging.getLogger(__name__)

# ─── Valid state transitions ───────────────────────────────────────────────────

ValidTransitions: dict[str, set[str]] = {
    "SPORE": {"HATCHING"},
    "HATCHING": {"ACTIVE", "REAPED"},
    "ACTIVE": {"STARVING", "CRYSTALLIZING", "REAPED"},
    "STARVING": {"REAPED", "ACTIVE", "CRYSTALLIZING"},
    "CRYSTALLIZING": {"REAPED"},
    "REAPED": set(),  # terminal
}


class InvalidTransitionError(RuntimeError):
    """Raised when a requested state transition is not permitted."""


class SwarmStateMachine:
    """
    Thread-safe state machine for validating and applying worker state transitions.

    Responsibility: Validate transitions against the rules table and fire
    registered callbacks after a transition is applied.

    This class holds NO worker data — only the transition rules and callback
    registry.  Worker data lives in WorkerPool.
    """

    def __init__(
        self,
        transitions: dict[str, set[str]] | None = None,
    ) -> None:
        self._transitions: dict[str, set[str]] = transitions or ValidTransitions
        self._lock = RLock()
        self._callbacks: list[
            Callable[[str, str, str], None]
        ] = []  # worker_id, old_state, new_state (all strings for serialisability)

    # ─── Public API ───────────────────────────────────────────────────────────

    def validate(
        self,
        current_state: str,
        desired_state: str,
    ) -> bool:
        """Return True if the transition is permitted, False otherwise."""
        with self._lock:
            allowed = self._transitions.get(current_state, set())
            return desired_state in allowed

    def transition(
        self,
        worker_id: str,
        old_state: str,
        new_state: str,
    ) -> None:
        """
        Apply a state transition after validating it.

        Raises:
            InvalidTransitionError: If the transition is not permitted.
        """
        with self._lock:
            allowed = self._transitions.get(old_state, set())
            if new_state not in allowed:
                raise InvalidTransitionError(
                    f"[SwarmStateMachine] Invalid transition: {old_state} -> {new_state} for worker='{worker_id}'"
                )

            callbacks = list(self._callbacks)

        _log.info(
            "[SwarmStateMachine] Worker '%s' %s -> %s",
            worker_id,
            old_state,
            new_state,
        )

        # Fire callbacks outside the lock to avoid deadlocks
        for cb in callbacks:
            try:
                cb(worker_id, old_state, new_state)
            except (TypeError, ValueError, AttributeError) as exc:
                _log.warning(
                    "[SwarmStateMachine] State-change callback error: %s",
                    exc,
                )

    def register_callback(
        self,
        callback: Callable[[str, str, str], None],
    ) -> None:
        """Register a callable invoked on every state transition.

        Signature: ``callback(worker_id: str, old_state: str, new_state: str)``
        """
        with self._lock:
            self._callbacks.append(callback)

    def unregister_callback(
        self,
        callback: Callable[[str, str, str], None],
    ) -> None:
        """Remove a previously registered callback."""
        with self._lock:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass
