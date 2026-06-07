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
# Watchdog ≡ Module
# 内涵 ≝ {Watchdog}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Watchdog)}
# 功能 ⊢ {Init_Watchdog, Execute_Watchdog, Validate_Watchdog}
# =============================================================================

"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: SwarmWatchdog — MetabolicWatchdog + NectarEngine + CrystallizationGate lifecycle.
  Extracted from SwarmLifecycleManager._ensure_watchdog(), _ensure_reward_engines(),
  _watchdog, _nectar_engine, _crystal_gate, watchdog.start()/shutdown().
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md

Responsibility: Single — manage the lifecycle (lazy init, start, shutdown) of
the MetabolicWatchdog daemon and reward engines. Does NOT perform monitoring
logic; that lives in MetabolicWatchdog itself.
"""

import logging
from collections.abc import Callable
from typing import Protocol

_log = logging.getLogger(__name__)


class MetabolicWatchdogProtocol(Protocol):
    def start(self) -> None: ...
    def shutdown(self) -> None: ...
    def watch(self, handle: WorkerHandle) -> None: ...
    def unwatch(self, worker_id: str) -> None: ...
    def set_state_callback(self, callback: Callable[..., None]) -> None: ...


class NectarEngineProtocol(Protocol):
    def process_reward(self, worker_id: str, amount: float) -> None: ...


class CrystallizationGateProtocol(Protocol):
    def crystallize(self, worker_id: str, score: float) -> None: ...


class SwarmWatchdog:
    """
    Lifecycle manager for MetabolicWatchdog and reward engines.

    Responsibility: Single — lazily create, start, and shut down the
    MetabolicWatchdog daemon thread and the optional NectarEngine +
    CrystallizationGate reward components.

    The actual monitoring logic lives in MetabolicWatchdog (from D-Economy).
    This class only manages their instantiation and lifecycle boundaries.
    """

    def __init__(
        self,
        state_callback: Callable[..., None] | None = None,
        *,
        has_watchdog: Callable[[], bool] | None = None,
        watchdog_factory: Callable[[], type[MetabolicWatchdogProtocol] | None] | None = None,
        has_reward_engines: Callable[[], bool] | None = None,
        nectar_engine_factory: Callable[[], type[NectarEngineProtocol] | None] | None = None,
        crystal_gate_factory: Callable[[], type[CrystallizationGateProtocol] | None] | None = None,
    ) -> None:
        self._watchdog: MetabolicWatchdogProtocol | None = None
        self._state_callback = state_callback
        self._nectar_engine: NectarEngineProtocol | None = None
        self._crystal_gate: CrystallizationGateProtocol | None = None
        self._started = False
        self._has_watchdog_override = has_watchdog
        self._watchdog_factory = watchdog_factory
        self._has_reward_engines_override = has_reward_engines
        self._nectar_engine_factory = nectar_engine_factory
        self._crystal_gate_factory = crystal_gate_factory

    # ─── Public API ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Lazily start MetabolicWatchdog if not already running."""
        if self._watchdog is not None or not self._has_watchdog_available():
            return
        try:
            watchdog_cls = self._resolve_watchdog_factory()
            if watchdog_cls is None:
                return

            self._watchdog = watchdog_cls()
            if self._state_callback is not None and hasattr(self._watchdog, "set_state_callback"):
                self._watchdog.set_state_callback(self._state_callback)
            self._watchdog.start()
            _log.info("[SwarmWatchdog] MetabolicWatchdog started.")
            self._started = True
        except (TypeError, ValueError, AttributeError, ImportError) as exc:
            _log.warning("[SwarmWatchdog] MetabolicWatchdog unavailable: %s", exc)
            self._watchdog = None

    def shutdown(self) -> None:
        """Stop the MetabolicWatchdog daemon thread."""
        if self._watchdog is None:
            return
        try:
            self._watchdog.shutdown()
        except (TypeError, ValueError, AttributeError) as exc:
            _log.debug("[SwarmWatchdog] Watchdog shutdown error: %s", exc)
        finally:
            self._watchdog = None

    @property
    def is_running(self) -> bool:
        """Return True if the watchdog daemon is active."""
        return self._watchdog is not None

    # ─── Reward engines ───────────────────────────────────────────────────────

    def ensure_reward_engines(self) -> None:
        """Lazily resolve NectarEngine and CrystallizationGate."""
        if (
            self._nectar_engine is not None and self._crystal_gate is not None
        ) or not self._has_reward_engines_available():
            return
        try:
            NectarEngine = self._load_nectar_engine()  # noqa: N806
            CrystallizationGate = self._load_crystal_gate()  # noqa: N806
            if NectarEngine is not None:
                self._nectar_engine = NectarEngine()
            if CrystallizationGate is not None:
                self._crystal_gate = CrystallizationGate()
            _log.info("[SwarmWatchdog] NectarEngine + CrystallizationGate ready.")
        except (TypeError, ValueError, AttributeError) as exc:
            _log.warning("[SwarmWatchdog] Reward engines unavailable: %s", exc)
            self._nectar_engine = None
            self._crystal_gate = None

    @property
    def nectar_engine(self) -> NectarEngineProtocol | None:
        """Return the NectarEngine instance (may be None)."""
        return self._nectar_engine

    @nectar_engine.setter
    def nectar_engine(self, engine: NectarEngineProtocol | None) -> None:
        self._nectar_engine = engine

    @property
    def crystal_gate(self) -> CrystallizationGateProtocol | None:
        """Return the CrystallizationGate instance (may be None)."""
        return self._crystal_gate

    @crystal_gate.setter
    def crystal_gate(self, gate: CrystallizationGateProtocol | None) -> None:
        self._crystal_gate = gate

    @property
    def raw_watchdog(self) -> MetabolicWatchdogProtocol | None:
        """Return the underlying MetabolicWatchdog instance."""
        return self._watchdog

    @raw_watchdog.setter
    def raw_watchdog(self, watchdog: MetabolicWatchdogProtocol | None) -> None:
        self._watchdog = watchdog

    # ─── Watchdog delegation ──────────────────────────────────────────────────

    def watch(self, handle: WorkerHandle) -> None:
        """Delegate to MetabolicWatchdog.watch if available."""
        if self._watchdog is not None:
            try:
                self._watchdog.watch(handle)
            except (TypeError, ValueError, AttributeError) as exc:
                _log.warning(
                    "[SwarmWatchdog] watch failed for '%s': %s",
                    handle.worker_id,
                    exc,
                )

    def unwatch(self, worker_id: str) -> None:
        """Delegate to MetabolicWatchdog.unwatch if available."""
        if self._watchdog is not None:
            try:
                self._watchdog.unwatch(worker_id)
            except (TypeError, ValueError, AttributeError) as exc:
                _log.debug(
                    "[SwarmWatchdog] unwatch skipped for '%s': %s",
                    worker_id,
                    exc,
                )

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _has_watchdog_available(self) -> bool:
        if self._has_watchdog_override is not None:
            return self._has_watchdog_override()
        return self._default_has_watchdog()

    def _has_reward_engines_available(self) -> bool:
        if self._has_reward_engines_override is not None:
            return self._has_reward_engines_override()
        return self._default_has_reward_engines()

    def _default_has_watchdog(self) -> bool:
        try:
            from nucleus.Z_Microkernel.organs.metabolic_watchdog import (  # type: ignore[import-not-found]  # noqa: F401
                MetabolicWatchdog,  # type: ignore[import-not-found]
            )  # type: ignore[import-not-found]

            return True
        except ImportError:
            return False

    def _default_has_reward_engines(self) -> bool:
        return self._load_nectar_engine() is not None or self._load_crystal_gate() is not None

    def _resolve_watchdog_factory(self) -> type[MetabolicWatchdogProtocol] | None:
        if self._watchdog_factory is not None:
            return self._watchdog_factory()
        try:
            from nucleus.Z_Microkernel.organs.metabolic_watchdog import (
                MetabolicWatchdog,
            )

            return MetabolicWatchdog
        except ImportError:
            return None

    def _load_nectar_engine(self) -> type[NectarEngineProtocol] | None:
        if self._nectar_engine_factory is not None:
            return self._nectar_engine_factory()
        try:
            return __import__(
                "organs.D_Economy.organs.nectar_engine",
                fromlist=["NectarEngine"],
            ).NectarEngine
        except (ImportError, AttributeError, TypeError, ValueError):
            return None

    def _load_crystal_gate(self) -> type[CrystallizationGateProtocol] | None:
        if self._crystal_gate_factory is not None:
            return self._crystal_gate_factory()
        try:
            return __import__(
                "organs.D_Genesis.organs.crystallization_gate",
                fromlist=["CrystallizationGate"],
            ).CrystallizationGate
        except (ImportError, AttributeError, TypeError, ValueError):
            return None
