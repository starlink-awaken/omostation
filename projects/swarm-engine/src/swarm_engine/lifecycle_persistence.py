from __future__ import annotations

from ._compat import WorkerHandle

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
# Persistence ≡ Module
# 内涵 ≝ {Persistence}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Persistence)}
# 功能 ⊢ {Init_Persistence, Execute_Persistence, Validate_Persistence}
# =============================================================================

"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: SwarmPersistence — SQLite WAL persistence for swarm worker state.
  Extracted from SwarmLifecycleManager._state_store usage (SwarmStateStore wrapper).
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md

Responsibility: Single — wrap SwarmStateStore and provide a clean facade.
Handles SQLite persistence for workers, task results, and state transitions.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


class SwarmPersistence:
    """
    SQLite WAL persistence facade for swarm worker lifecycle.

    Responsibility: Single — coordinate SQLite persistence via SwarmStateStore.
    All state mutations are audited in the state_transitions table.

    Usage::

        persistence = SwarmPersistence(db_path="/tmp/swarm.db")
        persistence.save_worker(handle)
        persistence.record_transition(worker_id, "ACTIVE", "REAPED")
        persistence.close()
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        state_store: Any | None = None,
    ) -> None:
        """
        Args:
            db_path:      Path to the SQLite database file.
            state_store:  Optional pre-instantiated SwarmStateStore (for DI).
                          If not provided, a new SwarmStateStore is created
                          from db_path.
        """
        self._store: Any | None = None

        if state_store is not None:
            self._store = state_store
        elif db_path is not None:
            try:
                from .organs.engine.swarm_state_store import (  # type: ignore[import-not-found]
                    SwarmStateStore,
                )

                self._store = SwarmStateStore(db_path)
                _log.debug("[SwarmPersistence] SwarmStateStore initialised (db=%s)", db_path)
            except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
                _log.warning(
                    "[SwarmPersistence] SwarmStateStore unavailable: %s — persistence disabled",
                    exc,
                )
                self._store = None
        else:
            _log.debug("[SwarmPersistence] No db_path provided — persistence disabled")

    # ─── Worker persistence ───────────────────────────────────────────────────

    def save_worker(self, handle: WorkerHandle) -> None:
        """Persist a worker handle to SQLite."""
        if self._store is None:
            return
        try:
            self._store.save_worker(handle)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError, sqlite3.Error):
            _log.debug("[SwarmPersistence] save_worker failed")

    def mark_reaped(self, worker_id: str) -> None:
        """Mark a worker as REAPED in the database."""
        if self._store is None:
            return
        try:
            self._store.mark_reaped(worker_id)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError, sqlite3.Error):
            _log.debug("[SwarmPersistence] mark_reaped failed for '%s'", worker_id)

    def record_transition(
        self,
        worker_id: str,
        from_state: str,
        to_state: str,
        reason: str = "",
    ) -> None:
        """Append a state transition to the audit trail."""
        if self._store is None:
            return
        try:
            self._store.record_transition(worker_id, from_state, to_state, reason=reason)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError, sqlite3.Error):
            _log.debug("[SwarmPersistence] record_transition failed for '%s'", worker_id)

    def save_task_result(
        self,
        worker_id: str,
        result: dict[str, Any],
    ) -> None:
        """Persist a task result dict to SQLite."""
        if self._store is None:
            return
        try:
            self._store.save_task_result(worker_id, result)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError, sqlite3.Error):
            _log.debug(
                "[SwarmPersistence] save_task_result failed for '%s'",
                worker_id,
            )

    # ─── Recovery ─────────────────────────────────────────────────────────────

    def get_recovery_candidates(self) -> list[dict[str, Any]]:
        """Return workers that were ACTIVE or HATCHING at last crash."""
        if self._store is None:
            return []
        try:
            return self._store.get_recovery_candidates()
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError, sqlite3.Error):
            _log.debug("[SwarmPersistence] get_recovery_candidates failed")
            return []

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._store is not None:
            try:
                self._store.close()
            except (OSError, sqlite3.Error):
                pass
            self._store = None
            _log.debug("[SwarmPersistence] Closed.")

    @property
    def is_available(self) -> bool:
        """Return True if persistence is enabled."""
        return self._store is not None
