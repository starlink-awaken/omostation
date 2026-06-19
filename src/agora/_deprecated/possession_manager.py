from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Gateway/AGENTS.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Possession Manager ≡ Module
# 内涵 ≝ {PossessionManager, PossessionSession, PossessionError}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, PossessionManager)}
# 功能 ⊢ {Enter_Possession, Exit_Possession, Evict_Possession, Heartbeat}
# =============================================================================

"""
---
Type: organ
Status: active
Layer: D-Gateway
Summary: Thread-safe agent possession lifecycle manager for B-OS role sessions.
Owner: SharedBrain
Version: 1.0.0
Authority: organs/D-Gateway/AGENTS.md
---

Possession Lifecycle
--------------------
Each node enforces a single-possession invariant: at most one
``PossessionSession`` may be POSSESSED at any time.

State Machine::

    IDLE  ──enter_possession()──►  POSSESSED
                                       │
                             ┌─────────┴──────────┐
                    exit_possession()    evict_possession()
                             │                    │
                             ▼                    ▼
                            IDLE              EVICTED

TTL Expiry (passive)::

    POSSESSED ──[TTL exceeded, next method call]──► EXPIRED

Environment Variables
---------------------
On ``enter_possession``:
    BOS_ROLE_ID      — role identifier string
    BOS_ROLE_CONTEXT — JSON-serialised role_context() dict

On ``exit_possession`` / ``evict_possession``:
    Both variables are removed from ``os.environ``.

Thread Safety
-------------
All public methods acquire ``_lock`` (``threading.RLock``) before
reading or mutating internal state.  The RLock allows re-entrant
acquisition from the same thread without deadlock.
"""

import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from abc import ABC, abstractmethod  # noqa: E402
from collections.abc import Callable  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any  # noqa: E402

# ===========================================================================
# Local type definitions (migrated from nucleus.Z_Spore.interfaces.possession)
# ===========================================================================


class PossessionState(Enum):
    IDLE = "IDLE"
    POSSESSED = "POSSESSED"
    EVICTED = "EVICTED"
    EXPIRED = "EXPIRED"


@dataclass
class PossessionSession:
    """Represents a single active agent possession session."""

    session_id: str
    role_id: str
    soul_data: dict[str, Any]
    state: PossessionState = field(default=PossessionState.POSSESSED)
    started_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    ttl_seconds: float = 3600.0

    @property
    def is_active(self) -> bool:
        return self.state == PossessionState.POSSESSED

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.started_at) > self.ttl_seconds

    def role_context(self) -> dict[str, Any]:
        identity = self.soul_data.get("identity", {})
        cockpit_mode = bool(identity.get("cockpit_mode", False))
        return {
            "role_id": self.role_id,
            "session_id": self.session_id,
            "node_id": identity.get("node_id", self.role_id),
            "owner_id": identity.get("owner_id", identity.get("owner", "")),
            "parent_node_id": identity.get("parent_node_id", ""),
            "run_mode": "possession",
            "hive_id": identity.get("hive_id", identity.get("governance_scope", "")),
            "risk_tier": identity.get("risk_tier", "standard"),
            "governance_scope": identity.get("governance_scope", ""),
            "sovereignty_level": identity.get("sovereignty_level", ""),
            "cockpit_mode": cockpit_mode,
            "control_plane": "cockpit" if cockpit_mode else "passive",
            "controller_session_id": self.session_id if cockpit_mode else "",
            "controller_node_id": str(identity.get("node_id", ""))
            if cockpit_mode
            else "",
            "controlled_worker_ids": self.soul_data.get("_controlled_worker_ids", []),
            "binding_mode": "exclusive-single-session",
            "session_kind": "cockpit" if cockpit_mode else "worker-bound",
            "persona": identity.get("persona", ""),
            "name": identity.get("name", ""),
            "avatar_type": identity.get("avatar_type", ""),
            "capabilities": identity.get(
                "capabilities", self.soul_data.get("capabilities", [])
            ),
            "constraints": self.soul_data.get("constraints", []),
            "soul_md": self.soul_data.get("_soul_md", ""),
            "soul_path": self.soul_data.get("_soul_path", ""),
            "level_system": self.soul_data.get("level_system", {}),
            "xp_rules": self.soul_data.get("xp_rules", {}),
            "personality": self.soul_data.get("personality", {}),
            "permissions": self.soul_data.get("permissions", {}),
        }

    def runtime_projection(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "role_id": self.role_id,
            "state": self.state.value,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "ttl_seconds": self.ttl_seconds,
            "role_context": self.role_context(),
            "source_type": "possession_runtime_projection",
            "status": self.state.value,
            "updated_at": self.last_heartbeat,
        }


class IPossessionManager(ABC):
    """Abstract contract for agent possession lifecycle management."""

    @abstractmethod
    def enter_possession(self, soul_data: dict[str, Any]) -> PossessionSession: ...
    @abstractmethod
    def exit_possession(self, session_id: str) -> None: ...
    @abstractmethod
    def evict_possession(self, session_id: str, reason: str) -> None: ...
    @abstractmethod
    def get_current_session(self) -> PossessionSession | None: ...
    @abstractmethod
    def get_current_runtime_projection(self) -> dict[str, Any] | None: ...
    @abstractmethod
    def heartbeat(self, session_id: str) -> None: ...
    @abstractmethod
    def is_possessed(self) -> bool: ...


__all__ = [
    "PossessionManager",
    "PossessionError",
    "PossessionSession",  # re-exported for test convenience
    "register_soul_context_callback",
]

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Soul-context callback registry
# ---------------------------------------------------------------------------
# Decoupled from D-Execution: SwarmLifecycleManager registers its
# ``set_soul_context`` on startup; PossessionManager calls it on
# enter/exit/evict without importing D-Execution directly.
# ---------------------------------------------------------------------------
_soul_context_callbacks: list[Callable[[dict | None], None]] = []
_soul_context_callbacks_lock = threading.Lock()


def register_soul_context_callback(fn: Callable[[dict | None], None]) -> None:
    """Register a callable that receives the soul context dict on possession changes.

    Args:
        fn: Called with the full ``role_context()`` dict on ``enter_possession``,
            or ``None`` on ``exit_possession`` / ``evict_possession``.
    """
    with _soul_context_callbacks_lock:
        _soul_context_callbacks.append(fn)


def _notify_soul_context(soul_context: dict | None) -> None:
    """Invoke all registered soul-context callbacks (best-effort)."""
    with _soul_context_callbacks_lock:
        callbacks = list(_soul_context_callbacks)
    for fn in callbacks:
        try:
            fn(soul_context)
        except Exception as exc:
            _log.warning(
                "PossessionManager: soul_context callback %r raised: %s", fn, exc
            )


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class PossessionError(Exception):
    """Raised for invalid possession lifecycle operations.

    Examples
    --------
    * Attempting to enter possession while a session is already active
      (double-possession guard).
    * Calling ``exit_possession`` / ``evict_possession`` / ``heartbeat``
      with a ``session_id`` that does not match the current session.
    * Passing ``soul_data`` that is missing the required ``"identity"`` key.
    """


# ---------------------------------------------------------------------------
# Manager implementation
# ---------------------------------------------------------------------------


class PossessionManager(IPossessionManager):
    """Concrete, thread-safe implementation of :class:`IPossessionManager`.

    Enforces the single-possession invariant, manages environment variables
    for role context injection, and passively expires sessions that exceed
    their TTL.

    Usage::

        pm = PossessionManager()
        session = pm.enter_possession(soul_data)
        # … work under possession …
        pm.exit_possession(session.session_id)
    """

    def __init__(self) -> None:
        self.status = "active"
        self._lock: threading.RLock = threading.RLock()
        self._session: PossessionSession | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_and_expire(self) -> None:
        """Auto-expire the current session if its TTL has been exceeded.

        Must be called while holding ``_lock``.
        """
        if self._session is not None and self._session.is_expired:
            _log.warning(
                "PossessionManager: session %s exceeded TTL (%.1f s) — auto-expiring.",
                self._session.session_id,
                self._session.ttl_seconds,
            )
            self._session.state = PossessionState.EXPIRED
            self._clear_env()
            self._session = None

    @staticmethod
    def _set_env(session: PossessionSession) -> None:
        """Inject role context into the process environment."""
        os.environ["BOS_ROLE_ID"] = session.role_id
        os.environ["BOS_ROLE_CONTEXT"] = json.dumps(session.role_context())

    @staticmethod
    def _clear_env() -> None:
        """Remove B-OS role context variables from the process environment."""
        os.environ.pop("BOS_ROLE_ID", None)
        os.environ.pop("BOS_ROLE_CONTEXT", None)

    # ------------------------------------------------------------------
    # IPossessionManager implementation
    # ------------------------------------------------------------------

    def enter_possession(self, soul_data: dict[str, Any]) -> PossessionSession:
        """Begin a new possession session.

        Args:
            soul_data: Validated soul payload.  Must be a ``dict`` containing
                an ``"identity"`` key.

        Returns:
            A :class:`PossessionSession` in ``POSSESSED`` state.

        Raises:
            PossessionError: If ``soul_data`` is invalid, or a session is
                already active (double-possession blocked).
        """
        # --- validation (before lock to keep the critical section short) ---
        if not isinstance(soul_data, dict):
            raise PossessionError(
                f"soul_data must be a dict, got {type(soul_data).__name__!r}"
            )
        if "identity" not in soul_data:
            raise PossessionError("soul_data is missing required 'identity' key")

        with self._lock:
            self._check_and_expire()
            if self._session is not None:
                raise PossessionError(
                    f"Double-possession blocked: session {self._session.session_id!r} "
                    "is already active.  Call exit_possession() first."
                )

            role_id: str = soul_data.get("identity", {}).get("role_id", "unknown")
            session_id: str = str(uuid.uuid4())
            session = PossessionSession(
                session_id=session_id,
                role_id=role_id,
                soul_data=soul_data,
                state=PossessionState.POSSESSED,
                started_at=time.time(),
                last_heartbeat=time.time(),
            )
            self._session = session
            self._set_env(session)

            _log.info(
                "PossessionManager: entered possession — session=%s role=%s",
                session_id,
                role_id,
            )

        # Notify soul-context callbacks outside the lock (non-fatal)
        _notify_soul_context(session.role_context())

        return session

    def exit_possession(self, session_id: str) -> None:
        """Gracefully terminate the active possession session.

        Transitions state to IDLE (manager holds no active session) and
        removes role context environment variables.

        Args:
            session_id: Must match the ID of the currently active session.

        Raises:
            PossessionError: If *session_id* does not match.
        """
        with self._lock:
            self._check_and_expire()
            if self._session is None or self._session.session_id != session_id:
                raise PossessionError(
                    f"exit_possession: no active session matching id={session_id!r}"
                )

            _log.info(
                "PossessionManager: exiting possession — session=%s role=%s",
                self._session.session_id,
                self._session.role_id,
            )
            self._session.state = PossessionState.IDLE
            self._session = None
            self._clear_env()

        # Notify soul-context callbacks outside the lock (non-fatal)
        _notify_soul_context(None)

    def evict_possession(self, session_id: str, reason: str) -> None:
        """Force-terminate a possession session regardless of its state.

        The session's state is set to ``EVICTED`` and both environment
        variables are cleared.  Unlike :meth:`exit_possession`, eviction
        always records *reason* in the log.

        Args:
            session_id: The session to evict.
            reason:     Reason string recorded in the audit log.

        Raises:
            PossessionError: If *session_id* does not match any known session.
        """
        with self._lock:
            # Do NOT call _check_and_expire here — we want to evict even
            # sessions that happen to be expired but are still referenced.
            if self._session is None or self._session.session_id != session_id:
                raise PossessionError(
                    f"evict_possession: no session matching id={session_id!r} — reason={reason!r}"
                )

            _log.warning(
                "PossessionManager: EVICTING session=%s role=%s reason=%r",
                self._session.session_id,
                self._session.role_id,
                reason,
            )
            self._session.state = PossessionState.EVICTED
            self._session = None
            self._clear_env()

        # Notify soul-context callbacks outside the lock (non-fatal)
        _notify_soul_context(None)

    def get_current_session(self) -> PossessionSession | None:
        """Return the currently active session, or ``None``.

        If the session has exceeded its TTL it is auto-expired and ``None``
        is returned.
        """
        with self._lock:
            self._check_and_expire()
            return self._session

    def get_current_runtime_projection(self) -> dict[str, Any] | None:
        """Return the formal runtime projection for the active possession.

        This gives callers a structured possession surface without requiring
        them to read ``BOS_ROLE_CONTEXT`` from process environment variables.
        """
        with self._lock:
            self._check_and_expire()
            if self._session is None:
                return None
            return self._session.runtime_projection()

    def heartbeat(self, session_id: str) -> None:
        """Refresh the ``last_heartbeat`` for the active session.

        Args:
            session_id: Must match the currently active session.

        Raises:
            PossessionError: If *session_id* does not match.
        """
        with self._lock:
            self._check_and_expire()
            if self._session is None or self._session.session_id != session_id:
                raise PossessionError(
                    f"heartbeat: no active session matching id={session_id!r}"
                )
            self._session.last_heartbeat = time.time()
            _log.debug(
                "PossessionManager: heartbeat — session=%s ts=%.3f",
                session_id,
                self._session.last_heartbeat,
            )

    def is_possessed(self) -> bool:
        """Return ``True`` if a non-expired active session exists."""
        with self._lock:
            self._check_and_expire()
            return self._session is not None and self._session.is_active
