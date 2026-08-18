from __future__ import annotations

"""
---
Type: Engine Component
Status: Active
Layer: L3
Summary: PossessionMultiSession — concurrent role-session management with priority-based
  conflict resolution and resource isolation for parallel agent possession.
Owner: bos-core
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Possession Multi Session ≡ Module
# 内涵 ≝ {Possession, Multi, Session}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, PossessionMultiSession)}
# 功能 ⊢ {Possession_Multi, Multi_Session, Session_Init}
# =============================================================================


import logging
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ───────────────────────────────────────────────────────────────────────────
# Data types
# ───────────────────────────────────────────────────────────────────────────


class SessionPriority(IntEnum):
    """Priority levels for possession sessions (higher value = higher priority)."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class PossessionSession:
    """Represents a single role-possession session."""

    session_id: str
    role_id: str
    priority: SessionPriority
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    resource_quota: dict[str, Any] = field(default_factory=dict)
    isolated: bool = False
    controller_session_id: str = ""
    worker_session_ids: list[str] = field(default_factory=list)


# ───────────────────────────────────────────────────────────────────────────
# Core class
# ───────────────────────────────────────────────────────────────────────────


class PossessionMultiSession:
    """Manages multiple concurrent role-possession sessions.

    Features:
        * Priority-based ordering and conflict resolution.
        * Resource isolation checks for isolated sessions.
        * Thread-safe via :class:`threading.Lock`.

    Usage::

        mgr = PossessionMultiSession()
        sess = mgr.create_session("s1", "analyst", SessionPriority.HIGH, {"gpu": 1})
        mgr.switch_session("s1")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, PossessionSession] = {}
        self._active_session_id: str | None = None

    # ── CRUD ──────────────────────────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        role_id: str,
        priority: SessionPriority = SessionPriority.NORMAL,
        resource_quota: dict[str, Any] | None = None,
        isolated: bool = False,
    ) -> PossessionSession:
        """Create and register a new possession session.

        Raises:
            ValueError: If *session_id* already exists.
        """
        with self._lock:
            if session_id in self._sessions:
                msg = f"Session '{session_id}' already exists"
                raise ValueError(msg)
            session = PossessionSession(
                session_id=session_id,
                role_id=role_id,
                priority=priority,
                resource_quota=resource_quota or {},
                isolated=isolated,
            )
            self._sessions[session_id] = session
            _log.debug("Created session %s (role=%s, priority=%s)", session_id, role_id, priority.name)
            return session

    def destroy_session(self, session_id: str) -> None:
        """Remove a session. Clears active if it was the active session.

        Raises:
            KeyError: If *session_id* does not exist.
        """
        with self._lock:
            if session_id not in self._sessions:
                msg = f"Session '{session_id}' not found"
                raise KeyError(msg)
            self._detach_session_locked(session_id)
            del self._sessions[session_id]
            if self._active_session_id == session_id:
                self._active_session_id = None
            _log.debug("Destroyed session %s", session_id)

    def get_session(self, session_id: str) -> PossessionSession | None:
        """Return the session object or ``None``."""
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[PossessionSession]:
        """Return all sessions (unordered snapshot)."""
        with self._lock:
            return list(self._sessions.values())

    # ── Ordering / active ─────────────────────────────────────────────────

    def get_active_sessions(self) -> list[PossessionSession]:
        """Sessions ordered by priority desc, then last_active desc."""
        with self._lock:
            return sorted(
                self._sessions.values(),
                key=lambda s: (s.priority, s.last_active),
                reverse=True,
            )

    def switch_session(self, session_id: str) -> None:
        """Set *session_id* as the currently active session.

        Raises:
            KeyError: If session does not exist.
        """
        with self._lock:
            if session_id not in self._sessions:
                msg = f"Session '{session_id}' not found"
                raise KeyError(msg)
            self._active_session_id = session_id
            self._sessions[session_id].last_active = time.time()

    def get_active(self) -> str | None:
        """Return the active session id, or ``None``."""
        with self._lock:
            return self._active_session_id

    # ── Controller / worker topology ─────────────────────────────────────

    def bind_controller_worker(self, controller_session_id: str, worker_session_id: str) -> None:
        """Bind a worker session to a controller session."""
        with self._lock:
            controller = self._sessions.get(controller_session_id)
            worker = self._sessions.get(worker_session_id)
            if controller is None:
                msg = f"Session '{controller_session_id}' not found"
                raise KeyError(msg)
            if worker is None:
                msg = f"Session '{worker_session_id}' not found"
                raise KeyError(msg)

            previous_controller_id = worker.controller_session_id
            if previous_controller_id and previous_controller_id != controller_session_id:
                previous_controller = self._sessions.get(previous_controller_id)
                if previous_controller is not None and worker_session_id in previous_controller.worker_session_ids:
                    previous_controller.worker_session_ids.remove(worker_session_id)

            worker.controller_session_id = controller_session_id
            if worker_session_id not in controller.worker_session_ids:
                controller.worker_session_ids.append(worker_session_id)
            _log.debug(
                "Bound worker session %s to controller session %s",
                worker_session_id,
                controller_session_id,
            )

    def unbind_controller_worker(self, controller_session_id: str, worker_session_id: str) -> None:
        """Remove a controller/worker binding."""
        with self._lock:
            controller = self._sessions.get(controller_session_id)
            worker = self._sessions.get(worker_session_id)
            if controller is None:
                msg = f"Session '{controller_session_id}' not found"
                raise KeyError(msg)
            if worker is None:
                msg = f"Session '{worker_session_id}' not found"
                raise KeyError(msg)

            if worker.controller_session_id == controller_session_id:
                worker.controller_session_id = ""
            if worker_session_id in controller.worker_session_ids:
                controller.worker_session_ids.remove(worker_session_id)
            _log.debug(
                "Unbound worker session %s from controller session %s",
                worker_session_id,
                controller_session_id,
            )

    def get_controller_session(self, worker_session_id: str) -> PossessionSession | None:
        """Return the controller session for *worker_session_id* if any."""
        with self._lock:
            worker = self._sessions.get(worker_session_id)
            if worker is None or not worker.controller_session_id:
                return None
            return self._sessions.get(worker.controller_session_id)

    def get_worker_sessions(self, controller_session_id: str) -> list[PossessionSession]:
        """Return all worker sessions bound to *controller_session_id*."""
        with self._lock:
            controller = self._sessions.get(controller_session_id)
            if controller is None:
                msg = f"Session '{controller_session_id}' not found"
                raise KeyError(msg)
            return [
                session
                for session_id in controller.worker_session_ids
                if (session := self._sessions.get(session_id)) is not None
            ]

    # ── Conflict resolution ───────────────────────────────────────────────

    def resolve_conflict(self, session_a: str, session_b: str) -> str:
        """Return the *session_id* that wins a conflict.

        Higher priority wins; ties broken by older ``created_at``.

        Raises:
            KeyError: If either session does not exist.
        """
        with self._lock:
            a = self._sessions.get(session_a)
            b = self._sessions.get(session_b)
            if a is None:
                msg = f"Session '{session_a}' not found"
                raise KeyError(msg)
            if b is None:
                msg = f"Session '{session_b}' not found"
                raise KeyError(msg)
            if a.priority != b.priority:
                return session_a if a.priority > b.priority else session_b
            # Same priority — older session wins (lower created_at).
            return session_a if a.created_at <= b.created_at else session_b

    # ── Resource isolation ────────────────────────────────────────────────

    def check_resource_isolation(self, session_id: str) -> bool:
        """Return ``True`` if isolated session has no resource-key overlap with others.

        Non-isolated sessions always return ``True``.

        Raises:
            KeyError: If session does not exist.
        """
        with self._lock:
            target = self._sessions.get(session_id)
            if target is None:
                msg = f"Session '{session_id}' not found"
                raise KeyError(msg)
            if not target.isolated:
                return True
            target_keys = set(target.resource_quota.keys())
            if not target_keys:
                return True
            for sid, sess in self._sessions.items():
                if sid == session_id:
                    continue
                if sess.isolated and target_keys & set(sess.resource_quota.keys()):
                    return False
            return True

    # ── Mutation helpers ──────────────────────────────────────────────────

    def update_activity(self, session_id: str) -> None:
        """Refresh ``last_active`` to *now*.

        Raises:
            KeyError: If session does not exist.
        """
        with self._lock:
            if session_id not in self._sessions:
                msg = f"Session '{session_id}' not found"
                raise KeyError(msg)
            self._sessions[session_id].last_active = time.time()

    def set_priority(self, session_id: str, new_priority: SessionPriority) -> None:
        """Change session priority.

        Raises:
            KeyError: If session does not exist.
        """
        with self._lock:
            if session_id not in self._sessions:
                msg = f"Session '{session_id}' not found"
                raise KeyError(msg)
            self._sessions[session_id].priority = new_priority
            _log.debug("Session %s priority → %s", session_id, new_priority.name)

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_session_stats(self) -> dict[str, Any]:
        """Return aggregated statistics about current sessions."""
        with self._lock:
            counts: dict[str, int] = {p.name: 0 for p in SessionPriority}
            for sess in self._sessions.values():
                counts[sess.priority.name] += 1
            return {
                "total": len(self._sessions),
                "active": self._active_session_id,
                "counts_per_priority": counts,
                "controller_count": sum(1 for sess in self._sessions.values() if sess.worker_session_ids),
                "worker_count": sum(1 for sess in self._sessions.values() if sess.controller_session_id),
            }

    def _detach_session_locked(self, session_id: str) -> None:
        """Detach a session from controller/worker relationships before deletion."""
        session = self._sessions.get(session_id)
        if session is None:
            return

        if session.controller_session_id:
            controller = self._sessions.get(session.controller_session_id)
            if controller is not None and session_id in controller.worker_session_ids:
                controller.worker_session_ids.remove(session_id)
            session.controller_session_id = ""

        for worker_session_id in list(session.worker_session_ids):
            worker = self._sessions.get(worker_session_id)
            if worker is not None and worker.controller_session_id == session_id:
                worker.controller_session_id = ""
            if worker_session_id in session.worker_session_ids:
                session.worker_session_ids.remove(worker_session_id)
