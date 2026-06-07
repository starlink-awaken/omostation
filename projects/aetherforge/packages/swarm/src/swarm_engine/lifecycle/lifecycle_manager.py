from __future__ import annotations

from ._compat import _log

"""
---
Type: Organ
Status: Active
Layer: L3
Summary: Swarm lifecycle manager — SOLID-refactored composition orchestrator.
  This file was extracted and refactored from the original
  swarm_lifecycle_manager.py (1222 lines) into single-responsibility
  components in the ``lifecycle`` subpackage.
Version: 1.1.0
Owner: bos-core
Authority: organs/D-Execution/AGENTS.md
---

Architecture
------------
SwarmLifecycleManager is now a thin orchestrator that composes:

- WorkerPool      → worker registry, heartbeats, task results
- SwarmStateMachine → state transition validation + callbacks
- ClusterCoordinator → cluster/federation topology
- SwarmPersistence  → SQLite WAL persistence
- SwarmWatchdog    → MetabolicWatchdog + reward engine lifecycle
- SwarmEventEmitter → EventBus integration

Each component is injected via constructor (dependency injection) so they
can be mocked in tests and replaced independently.
"""

# ─── stdlib ───────────────────────────────────────────────────────────────────
import importlib
import logging
import sys
import time
import types
import uuid
from collections.abc import Callable
from pathlib import Path
from threading import RLock

# ─── nucleus ──────────────────────────────────────────────────────────────────
from typing import TYPE_CHECKING as _TC
from typing import Any

if _TC:
    from nucleus.Z_Microkernel.organs.swarm_types import (  # type: ignore[import-not-found]
        ISwarmLifecycle,
        TaskResult,
        WorkerBundle,
        WorkerHandle,
        WorkerState,
    )
# Runtime fallback — nucleus may not be available
from enum import StrEnum
from typing import Protocol, runtime_checkable


@runtime_checkable
class ISwarmLifecycle(Protocol):  # type: ignore[no-redef]
    def hatch(self, *a: Any, **kw: Any) -> Any: ...
    def reap(self, *a: Any, **kw: Any) -> Any: ...
    def list_active(self, *a: Any, **kw: Any) -> Any: ...


class TaskResult:  # type: ignore[no-redef]
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    worker_id: str = ""
    task_id: str = ""
    success: bool = True
    output: str = ""
    eu_consumed: float = 0.0
    duration_s: float = 0.0
    quality_score: float = 0.0
    error: str = ""


class WorkerBundle:  # type: ignore[no-redef]
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    total_tasks: int = 0
    successful_tasks: int = 0
    total_eu_consumed: float = 0.0


class WorkerHandle:  # type: ignore[no-redef]
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    worker_id: str = ""
    pid: int = 0
    state: Any = None


class WorkerState(StrEnum):  # type: ignore[no-redef]
    HATCHING = "HATCHING"
    ACTIVE = "ACTIVE"
    STARVING = "STARVING"
    REAPED = "REAPED"


# ─── engine subcomponents (extracted) ────────────────────────────────────────
from .organs.engine.lifecycle.call_dispatcher import CallDispatcher  # type: ignore[import-not-found]
from .organs.engine.lifecycle.cluster import ClusterCoordinator  # type: ignore[import-not-found]
from .organs.engine.lifecycle.events import SwarmEventEmitter  # type: ignore[import-not-found]
from .organs.engine.lifecycle.governance import SwarmGovernance  # type: ignore[import-not-found]
from .organs.engine.lifecycle.parallel_dispatch import ParallelDispatch  # type: ignore[import-not-found]
from .organs.engine.lifecycle.persistence import SwarmPersistence  # type: ignore[import-not-found]
from .organs.engine.lifecycle.state_machine import (  # type: ignore[import-not-found]
    InvalidTransitionError,
    SwarmStateMachine,
)
from .organs.engine.lifecycle.watchdog import SwarmWatchdog  # type: ignore[import-not-found]
from .organs.engine.lifecycle.worker_pool import (  # type: ignore[import-not-found]
    WorkerNotFoundError,
    WorkerPool,
)
from .organs.engine.worker_hatch_attempt import WorkerHatchAttempt  # type: ignore[import-not-found]
from .organs.engine.worker_hatch_gatekeeper import (  # type: ignore[import-not-found]
    WorkerHatchGatekeeper,
)
from .organs.engine.worker_reap_orchestrator import (  # type: ignore[import-not-found]
    WorkerReapOrchestrator,
)
from .organs.swarm_worker_governance_controller import (  # type: ignore[import-not-found]
    WorkerGovernanceController,
)

_COMPAT_MODULE_NAME = "organs.D_Execution.organs.swarm_lifecycle_manager"

# ─── Soft-dependency imports ───────────────────────────────────────────────────
try:
    from .organs.engine.spore_registry import (  # type: ignore[import-not-found]
        SporeNotFoundError,
        SporeRegistry,
    )
except ImportError:
    from engine.spore_registry import SporeRegistry  # type: ignore[no-redef, import-not-found]

    SporeNotFoundError = Exception  # type: ignore[assignment,misc]

try:
    from .organs.engine.hatcher import (  # type: ignore[import-not-found]
        Hatcher,
        HatchError,
        HatchTimeoutError,
    )
except ImportError:
    from engine.hatcher import Hatcher  # type: ignore[no-redef, import-not-found]

    HatchError = Exception  # type: ignore[assignment,misc]
    HatchTimeoutError = Exception  # type: ignore[assignment,misc]

try:
    from .organs.engine.swarm_result_collector import (  # type: ignore[import-not-found]
        SwarmResultCollector,
    )

    _HAS_RESULT_COLLECTOR = True
except ImportError:
    try:
        from engine.swarm_result_collector import SwarmResultCollector  # type: ignore[no-redef, import-not-found]
    except ImportError:
        SwarmResultCollector = None  # type: ignore[assignment]
    _HAS_RESULT_COLLECTOR = False

try:
    from .organs.engine.consensus_monitor import ConsensusMonitor  # type: ignore[import-not-found]

    _HAS_CONSENSUS_MONITOR = True
except ImportError:
    try:
        from engine.consensus_monitor import ConsensusMonitor  # type: ignore[no-redef, import-not-found]
    except ImportError:
        ConsensusMonitor = None  # type: ignore[assignment]
    _HAS_CONSENSUS_MONITOR = False

try:
    from nucleus.Z_Microkernel.mesh.synapse.registry import get_synapse_registry  # type: ignore[import-not-found]

    _HAS_SYNAPSE_REGISTRY = True
except ImportError:
    get_synapse_registry = None  # type: ignore[assignment]
    _HAS_SYNAPSE_REGISTRY = False

_DEGRADED_RUNTIME_EU_CAP = 0.5

logger = logging.getLogger(__name__)


def _load_approval_router_module() -> types.ModuleType | None:
    try:
        compat_importlib: types.ModuleType = _compat_override("importlib", importlib)  # type: ignore[assignment]
        return compat_importlib.import_module("organs.D_Governance.organs.approval_router")
    except (ImportError, ModuleNotFoundError, AttributeError):
        raise


def _compat_override(name: str, default: Any) -> Any:
    compat_module = sys.modules.get(_COMPAT_MODULE_NAME)
    if compat_module is None:
        return default
    return getattr(compat_module, name, default)


# ──────────────────────────────────────────────────────────────────────────────
# SwarmLifecycleManager — refactored orchestrator
# ──────────────────────────────────────────────────────────────────────────────


class SwarmLifecycleManager(ISwarmLifecycle):
    """
    Thread-safe orchestrator for Swarm Worker lifecycle.

    Responsibilities (delegated to injected components):
    - WorkerPool        → worker registry, heartbeats, task result accumulation
    - SwarmStateMachine → state transition validation + callback dispatch
    - ClusterCoordinator → cluster/federation topology
    - SwarmPersistence   → SQLite WAL persistence
    - SwarmWatchdog     → MetabolicWatchdog + reward engine lifecycle
    - SwarmEventEmitter → EventBus lifecycle events

    Usage::

        manager = SwarmLifecycleManager()
        handle = manager.spawn("code.generation.python", eu_budget=5000.0, task_prompt="Write a sort")
        bundle = manager.reap(handle.worker_id)
    """

    def __init__(
        self,
        spore_registry: SporeRegistry | None = None,
        hatcher: Hatcher | None = None,
        db_path: str | Path | None = None,
        *,
        # ─── Injected sub-components (all optional — auto-instantiated if None) ─
        worker_pool: WorkerPool | None = None,
        state_machine: SwarmStateMachine | None = None,
        cluster_coordinator: ClusterCoordinator | None = None,
        persistence: SwarmPersistence | None = None,
        watchdog: SwarmWatchdog | None = None,
        event_emitter: SwarmEventEmitter | None = None,
    ) -> None:
        self._lock = RLock()

        # ─── Core sub-components (DI or auto-instantiate) ────────────────────
        self._pool = worker_pool or WorkerPool()
        self._state_machine = state_machine or SwarmStateMachine()
        self._cluster = cluster_coordinator or ClusterCoordinator()
        self._persistence = persistence or SwarmPersistence(db_path=db_path)
        self._watchdog_lifecycle = watchdog or SwarmWatchdog(
            state_callback=self.update_state,
            has_watchdog=lambda: bool(_compat_override("_HAS_WATCHDOG", False)),
            watchdog_factory=lambda: _compat_override("MetabolicWatchdog", None),  # type: ignore[return-value]
            has_reward_engines=lambda: bool(_compat_override("_HAS_REWARD_ENGINES", False)),
            nectar_engine_factory=lambda: _compat_override("NectarEngine", None),  # type: ignore[return-value]
            crystal_gate_factory=lambda: _compat_override("CrystallizationGate", None),  # type: ignore[return-value]
        )
        self._events = event_emitter or SwarmEventEmitter()

        # ─── Injected or auto-instantiated dependencies ─────────────────────
        self._spore_registry = spore_registry or SporeRegistry()
        self._hatcher = hatcher or Hatcher()

        # ─── Optional integrations ───────────────────────────────────────────
        self._synapse_registry: Any | None = None
        if _HAS_SYNAPSE_REGISTRY and get_synapse_registry is not None:
            try:
                self._synapse_registry = get_synapse_registry()
            except (TypeError, ValueError, AttributeError) as exc:
                logger.warning(
                    "[SwarmLifecycleManager] SynapseRegistry unavailable: %s",
                    exc,
                )

        # ─── Soul context (set by possession sessions) ────────────────────────
        self._soul_context: dict | None = None

        # ─── Result collector — lazy ─────────────────────────────────────────
        self._result_collector: Any | None = None

        # ─── ConsensusMonitor — lazy ─────────────────────────────────────────
        self._consensus_monitor: Any | None = None

        # ─── Call dispatcher (handles CoreService.call action routing) ────
        self._dispatcher = CallDispatcher(manager=self)

        # ─── Governance action handler ───────────────────────────────────────
        self._governor = SwarmGovernance(
            reap_fn=self.reap_by_id,
            transition_fn=self.update_state,
            governance_state_from_handle=WorkerGovernanceController.rebuild_governance_state,
            governance_project_onto_handle=WorkerGovernanceController.project_onto_handle,
            events_emit=self._events.emit,
        )

        # ─── Parallel dispatch ────────────────────────────────────────────────
        self._parallel = ParallelDispatch(
            spawn_fn=self.spawn,
            ensure_consensus_monitor_fn=self._ensure_consensus_monitor,
            get_consensus_monitor=lambda: self._consensus_monitor,
            events_emit=self._events.emit,
        )

        # ─── Expose cluster fields for backward compatibility ───────────────
        self._connectivity = self._cluster.connectivity
        self._nodes = self._cluster.nodes
        self._bootstrap_nodes = self._cluster.bootstrap_nodes

        # ─── Register state-change callback on state machine ─────────────────
        # Proxy the pool's heartbeat on every ACTIVE transition
        self._state_machine.register_callback(self._on_state_change_proxy)

        self.initialize()

    @property
    def _workers(self) -> dict[str, WorkerHandle] | object:
        """Legacy live view over active and reaped worker handles."""
        if not hasattr(self, "_pool"):
            if "_compat_workers" not in self.__dict__:  # type: ignore[index]
                self.__dict__["_compat_workers"] = {}  # type: ignore[index]
            return self.__dict__["_compat_workers"]  # type: ignore[return-value]
        return self._pool.legacy_workers()

    @_workers.setter
    def _workers(self, workers: dict[str, WorkerHandle] | object) -> None:
        if not hasattr(self, "_pool"):
            self.__dict__["_compat_workers"] = dict(workers)  # type: ignore[index]
            return
        with self._pool._lock:
            self._pool._workers = dict(workers)
            live_worker_ids = set(self._pool._workers)
            self._pool._bundles = {
                worker_id: bundle for worker_id, bundle in self._pool._bundles.items() if worker_id in live_worker_ids
            }
            self._pool._heartbeats = {
                worker_id: heartbeat
                for worker_id, heartbeat in self._pool._heartbeats.items()
                if worker_id in live_worker_ids
            }
            self._pool._thread_worker_ids = {
                worker_id for worker_id in self._pool._thread_worker_ids if worker_id in live_worker_ids
            }

    @property
    def _state_store(self) -> Any | None:
        """Backward-compatible alias for the underlying persistence store."""
        return getattr(self._persistence, "_store", None)

    @_state_store.setter
    def _state_store(self, state_store: Any | None) -> None:
        if isinstance(state_store, SwarmPersistence):
            self._persistence = state_store
            return
        self._persistence = SwarmPersistence(state_store=state_store)

    @property
    def _watchdog(self) -> Any | None:
        """Backward-compatible alias for the raw MetabolicWatchdog instance."""
        if not hasattr(self, "_watchdog_lifecycle"):
            return self.__dict__.get("_compat_watchdog")
        return self._watchdog_lifecycle.raw_watchdog

    @_watchdog.setter
    def _watchdog(self, watchdog: Any | None) -> None:
        if not hasattr(self, "_watchdog_lifecycle"):
            self.__dict__["_compat_watchdog"] = watchdog  # type: ignore[index]
            return
        self._watchdog_lifecycle.raw_watchdog = watchdog

    @property
    def _nectar_engine(self) -> Any | None:
        if not hasattr(self, "_watchdog_lifecycle"):
            return self.__dict__.get("_compat_nectar_engine")
        return self._watchdog_lifecycle.nectar_engine

    @_nectar_engine.setter
    def _nectar_engine(self, engine: Any | None) -> None:
        if not hasattr(self, "_watchdog_lifecycle"):
            self.__dict__["_compat_nectar_engine"] = engine  # type: ignore[index]
            return
        self._watchdog_lifecycle.nectar_engine = engine

    @property
    def _crystal_gate(self) -> Any | None:
        if not hasattr(self, "_watchdog_lifecycle"):
            return self.__dict__.get("_compat_crystal_gate")
        return self._watchdog_lifecycle.crystal_gate

    @_crystal_gate.setter
    def _crystal_gate(self, gate: Any | None) -> None:
        if not hasattr(self, "_watchdog_lifecycle"):
            self.__dict__["_compat_crystal_gate"] = gate  # type: ignore[index]
            return
        self._watchdog_lifecycle.crystal_gate = gate

    # ─── IOrgan lifecycle ─────────────────────────────────────────────────────

    def initialize(self) -> None:
        super().initialize()
        logger.info("[SwarmLifecycleManager] Initialized.")
        self._events.emit("swarm.started", {"status": "initialized"})

    def shutdown(self) -> None:
        """Reap all active workers on shutdown."""
        if self._result_collector is not None:
            self._result_collector.stop()
            self._result_collector = None

        for wid in self._pool.all_handles():
            h = self._pool.get_handle_unsafe(wid)
            if h is not None and h.state.name != "REAPED":
                try:
                    self.reap_by_id(wid, reason="SwarmLifecycleManager.shutdown")
                except (TypeError, ValueError, AttributeError) as exc:
                    logger.warning(
                        "[SwarmLifecycleManager] Shutdown reap error for %s: %s",
                        wid,
                        exc,
                    )

        self._watchdog_lifecycle.shutdown()
        self._persistence.close()

        super().shutdown()
        self._events.emit("swarm.stopped", {"status": "shutdown"})

    # ─── Cluster / Federation (delegated to ClusterCoordinator) ───────────────

    def init_cluster(self, bootstrap_nodes: list[str] | None = None) -> bool:
        """Initialize this node as part of a cluster."""
        result = self._cluster.initialize(
            bootstrap_nodes=bootstrap_nodes,
            logger=logger,
        )
        self._sync_cluster_fields()
        return result

    def discover_peers(self) -> list[str]:
        """Discover available peers via DHT or bootstrap list."""
        discovered = self._cluster.discover_peers(logger=logger)
        self._sync_cluster_fields()
        return discovered

    def sync_state(self, node_id: str) -> bool:
        """Synchronize local state with a remote node."""
        result = self._cluster.sync_state(node_id, logger=logger)
        self._sync_cluster_fields()
        return result

    def get_cluster_status(self) -> dict:
        """Get current cluster/federation status."""
        self._sync_cluster_fields()
        return self._cluster.get_status(
            active_worker_count=len([w for w in self._pool.all_handles().values() if w.state.name == "ACTIVE"]),
        )

    # ─── ISwarmLifecycle implementation ─────────────────────────────────────

    def hatch(
        self,
        spore_id: str,
        task_prompt: str,
        eu_budget: float,
        soul_context: dict | None = None,
    ) -> WorkerHandle:
        """Spawn a worker directly by spore_id (ISwarmLifecycle contract)."""
        spore_config = self._spore_registry.get_spore(spore_id)
        if eu_budget <= 0:
            eu_budget = float(spore_config.get("default_eu_budget", 1000.0))
        effective_soul = soul_context if soul_context is not None else self._soul_context
        return self._do_hatch(spore_config, task_prompt, eu_budget, soul_context=effective_soul)

    def reap(self, handle: WorkerHandle, reason: str = "explicit_reap") -> WorkerBundle:
        """Terminate worker referenced by handle."""
        return self.reap_by_id(handle.worker_id, reason=reason)

    def list_active(self) -> list[WorkerHandle]:
        """Return all workers in ACTIVE or STARVING state."""
        return self._pool.list_active()

    def list_active_threads(self) -> list[WorkerHandle]:
        """Return WorkerHandles for internal-thread workers in ACTIVE or STARVING."""
        return self._pool.list_active_threads()

    # ─── Extended public API ─────────────────────────────────────────────────

    def ping_heartbeat(self, worker_id: str) -> None:
        self._pool.ping_heartbeat(worker_id)

    def get_stale_workers(self) -> list[str]:
        return self._pool.get_stale_workers()

    def spawn(
        self,
        capability: str,
        eu_budget: float,
        task_prompt: str,
        cost_class: str | None = None,
        soul_context: dict | None = None,
    ) -> WorkerHandle:
        """Find the best spore by capability and hatch a new Worker."""
        spore_config = self._spore_registry.find_spore_by_capability(capability, cost_class=cost_class)
        if eu_budget <= 0:
            eu_budget = float(spore_config.get("default_eu_budget", 1000.0))
        effective_soul = soul_context if soul_context is not None else self._soul_context
        return self._do_hatch(spore_config, task_prompt, eu_budget, soul_context=effective_soul)

    def dispatch_parallel(
        self,
        capabilities: list[str],
        task_prompt: str,
        eu_budget: float = 0.0,
        consensus_threshold: float = 0.5,
        soul_context: dict | None = None,
    ) -> list[WorkerHandle]:
        """Spawn a parallel batch of workers and wire ConsensusMonitor for early stopping."""
        return self._parallel.dispatch(
            capabilities,
            task_prompt,
            eu_budget=eu_budget,
            consensus_threshold=consensus_threshold,
            soul_context=soul_context,
        )

    def set_soul_context(self, soul_context: dict | None) -> None:
        """Set the soul context for all subsequent worker spawns."""
        with self._lock:
            self._soul_context = soul_context
        if soul_context is not None:
            logger.info(
                "[SwarmLifecycleManager] Soul context set: role_id=%r",
                soul_context.get("role_id"),
            )
        else:
            logger.info("[SwarmLifecycleManager] Soul context cleared.")

    def apply_governance_action(
        self,
        worker_id: str,
        *,
        action: str,
        actor_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Apply a runtime governance action to a currently tracked worker."""
        handle = self._pool.get_handle(worker_id)
        return self._governor.apply(worker_id, handle, action=action, actor_id=actor_id, reason=reason)

    def reap_by_id(self, worker_id: str, reason: str = "explicit_reap") -> WorkerBundle:
        """Terminate a worker by ID and return its lifecycle bundle."""
        handle = self._pool.get_handle_unsafe(worker_id)
        if handle is None:
            raise WorkerNotFoundError(f"[SwarmLifecycleManager] Worker '{worker_id}' not found.")

        logger.info(
            "[SwarmLifecycleManager] Reaping worker='%s' state=%s reason='%s'",
            worker_id,
            handle.state.value,
            reason,
        )

        # Ensure reward engines are available before reap
        self._watchdog_lifecycle.ensure_reward_engines()

        bundle = WorkerReapOrchestrator().orchestrate_reap(
            worker_id=worker_id,
            reason=reason,
            unwatch_worker=(
                lambda wid: self._watchdog_lifecycle.unwatch(wid) if self._watchdog_lifecycle.is_running else None
            ),
            terminate_worker=lambda wid, reap_reason: self._hatcher.terminate(wid, reason=reap_reason),
            unregister_synapse=self._synapse_unregister,
            build_bundle=self._pool.build_bundle,
            ensure_reward_engines=self._watchdog_lifecycle.ensure_reward_engines,
            get_nectar_engine=lambda: self._watchdog_lifecycle.nectar_engine,
            get_crystal_gate=lambda: self._watchdog_lifecycle.crystal_gate,
            transition_state=lambda wid, new_state: self._state_machine.transition(
                wid,
                (
                    self._pool.get_handle_unsafe(wid).state.name  # type: ignore[union-attr]
                    if self._pool.get_handle_unsafe(wid) is not None
                    else ""
                ),
                new_state.name,
            ),
            mark_reaped=(self._persistence.mark_reaped if self._persistence.is_available else None),
            logger=logger,
            crystallizing_transition_errors=(InvalidTransitionError, WorkerNotFoundError),
        )

        # Persist transition to REAPED
        self._persistence.record_transition(
            worker_id,
            handle.state.name,
            "REAPED",
            reason=reason,
        )
        self._persistence.mark_reaped(worker_id)

        # Update pool
        handle.state = WorkerState.REAPED
        self._pool.store_bundle(worker_id, bundle)
        self._pool.unregister(worker_id)

        logger.info(
            "[SwarmLifecycleManager] Worker '%s' reaped. tasks=%d success=%d eu=%.1f",
            worker_id,
            bundle.total_tasks,
            bundle.successful_tasks,
            bundle.total_eu_consumed,
        )
        self._events.emit(
            "worker.terminated",
            {"worker_id": worker_id, "reason": reason, "tasks": bundle.total_tasks},
        )
        return bundle

    def update_state(self, worker_id: str, new_state: WorkerState) -> None:
        """Transition a worker to a new state."""
        old_state = self._pool.get_handle_unsafe(worker_id)
        if old_state is None:
            raise WorkerNotFoundError(f"[SwarmLifecycleManager] Cannot transition unknown worker='{worker_id}'")
        old_name = old_state.state.name

        # Validate + apply via state machine (raises InvalidTransitionError on bad transition)
        self._state_machine.transition(worker_id, old_name, new_state.name)

        # Update handle in pool
        old_state.state = new_state
        self._persistence.record_transition(worker_id, old_name, new_state.name)
        self._persistence.save_worker(old_state)

    def _transition_state(
        self,
        worker_id: str,
        new_state: WorkerState,
        _from: WorkerState | None = None,
    ) -> None:
        """Backward-compatible wrapper around update_state()."""
        if _from is None:
            self.update_state(worker_id, new_state)
            return

        handle = self._pool.get_handle_unsafe(worker_id)
        if handle is None:
            raise WorkerNotFoundError(f"[SwarmLifecycleManager] Cannot transition unknown worker='{worker_id}'")

        old_name = _from.name if hasattr(_from, "name") else str(_from)
        self._state_machine.transition(worker_id, old_name, new_state.name)
        handle.state = new_state
        self._persistence.record_transition(worker_id, old_name, new_state.name)
        self._persistence.save_worker(handle)

    def record_task_result(self, result: TaskResult) -> None:
        """Append a completed TaskResult to the worker's accumulating bundle data."""
        if hasattr(self, "_pool"):
            self._pool.record_task_result(result)
        else:
            if "_compat_workers" not in self.__dict__:  # type: ignore[index]
                self.__dict__["_compat_workers"] = {}  # type: ignore[index]
            workers: dict[str, Any] = self.__dict__["_compat_workers"]  # type: ignore[index]
            if result.worker_id not in workers:
                raise WorkerNotFoundError(
                    f"[SwarmLifecycleManager] Worker '{result.worker_id}' not found when recording task result."
                )
            handle = workers[result.worker_id]
            handle.eu_consumed += result.eu_consumed
            handle.last_heartbeat = time.time()
            if not hasattr(handle, "_task_results"):
                object.__setattr__(handle, "_task_results", [])
            handle._task_results.append(result)  # type: ignore[attr-defined]

        # Persist to SQLite
        if hasattr(self, "_persistence") and self._persistence.is_available:
            self._persistence.save_task_result(
                result.worker_id,
                {
                    "task_id": result.task_id,
                    "success": result.success,
                    "output": result.output,
                    "eu_consumed": result.eu_consumed,
                    "duration_s": result.duration_s,
                    "quality_score": result.quality_score,
                    "error": result.error,
                },
            )

        if hasattr(self, "_events"):
            self._events.emit(
                "task.result.recorded",
                {
                    "worker_id": result.worker_id,
                    "success": result.success,
                    "eu": result.eu_consumed,
                },
            )

        # Feed into ConsensusMonitor for early-stopping
        if self._consensus_monitor is not None:
            try:
                self._consensus_monitor.on_result(result)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass

    def touch_heartbeat(self, worker_id: str) -> None:
        """Update last_heartbeat timestamp for a worker."""
        self._pool.touch_heartbeat(worker_id)
        if self._persistence.is_available:
            handle = self._pool.get_handle_unsafe(worker_id)
            if handle is not None:
                self._persistence.save_worker(handle)

    def recover_from_crash(self) -> list[str]:
        """Load workers that were ACTIVE/HATCHING at last crash and mark them REAPED."""
        candidates = self._persistence.get_recovery_candidates()
        recovered_ids: list[str] = []
        for row in candidates:
            wid = row["worker_id"]
            self._persistence.record_transition(
                wid,
                row["state"],
                "REAPED",
                reason="crash_recovery",
            )
            self._persistence.mark_reaped(wid)
            recovered_ids.append(wid)
            logger.info(
                "[SwarmLifecycleManager] Crash recovery: marked worker '%s' as REAPED",
                wid,
            )
        return recovered_ids

    def register_state_change_callback(
        self,
        callback: Callable[[str, WorkerState, WorkerState], None],
    ) -> None:
        """Register a callable invoked on every state transition."""

        # Wrap the ISwarmLifecycle signature callback into the state-machine string signature
        def _wrap(
            worker_id: str,
            old_state: str,
            new_state: str,
        ) -> None:
            old_enum = WorkerState[old_state]
            new_enum = WorkerState[new_state]
            try:
                callback(worker_id, old_enum, new_enum)
            except (KeyError, TypeError, ValueError):
                pass

        self._state_machine.register_callback(_wrap)

    def get_handle(self, worker_id: str) -> WorkerHandle:
        """Retrieve a live WorkerHandle by ID."""
        return self._pool.get_handle(worker_id)

    def all_handles(self) -> dict[str, WorkerHandle]:
        """Return a snapshot copy of the internal workers dict."""
        return self._pool.all_handles()

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _sync_cluster_fields(self) -> None:
        """Mirror cluster coordinator state onto legacy manager attributes."""
        self._connectivity = self._cluster.connectivity
        self._nodes = self._cluster.nodes
        self._bootstrap_nodes = self._cluster.bootstrap_nodes

    def _ensure_result_collector(self) -> None:
        """Lazily start the result collector before workers can publish TaskResults."""
        collector_enabled = bool(_compat_override("_HAS_RESULT_COLLECTOR", _HAS_RESULT_COLLECTOR))
        collector_cls: Any = _compat_override("SwarmResultCollector", SwarmResultCollector)
        if self._result_collector is not None or not collector_enabled or collector_cls is None:
            return
        self._result_collector = collector_cls(result_callback=self._safe_record_task_result)
        if self._result_collector is not None:
            try:
                self._result_collector.start()
            except (TypeError, ValueError, AttributeError) as exc:
                logger.warning(
                    "[SwarmLifecycleManager] SwarmResultCollector failed to start: %s",
                    exc,
                )
                self._result_collector = None

    def _ensure_consensus_monitor(self) -> None:
        """Lazily instantiate ConsensusMonitor for parallel dispatch only."""
        monitor_enabled = bool(_compat_override("_HAS_CONSENSUS_MONITOR", _HAS_CONSENSUS_MONITOR))
        monitor_cls: Any = _compat_override("ConsensusMonitor", ConsensusMonitor)
        if self._consensus_monitor is not None or not monitor_enabled or monitor_cls is None:
            return
        try:
            self._consensus_monitor = monitor_cls(hatcher=self._hatcher)
            logger.info("[SwarmLifecycleManager] ConsensusMonitor ready.")
        except (TypeError, ValueError, AttributeError) as exc:
            logger.warning(
                "[SwarmLifecycleManager] ConsensusMonitor unavailable: %s",
                exc,
            )
            self._consensus_monitor = None

    def _safe_record_task_result(self, result: TaskResult) -> None:
        """Callback shim used by SwarmResultCollector."""
        try:
            self.record_task_result(result)
        except WorkerNotFoundError:
            logger.debug(
                "[SwarmLifecycleManager] TaskResult for unregistered worker '%s' "
                "received via bus — ignored (CLI worker not tracked by this manager).",
                result.worker_id,
            )

    def _do_hatch(
        self,
        spore_config: dict[str, Any],
        task_prompt: str,
        eu_budget: float,
        soul_context: dict | None = None,
    ) -> WorkerHandle:
        """Common hatch path: gatekeep, attempt, finalise."""
        spore_id = spore_config.get("id", "unknown")

        WorkerHatchGatekeeper().enforce_hatch_gates(
            spore_id=spore_id,
            spore_config=spore_config,
            workers=self._pool.all_handles(),
            lock=RLock(),  # pool uses its own internal lock
            load_approval_router=_load_approval_router_module,
            logger=_log,
        )

        # Register a placeholder in HATCHING state
        placeholder_id = f"worker_{spore_id}_{uuid.uuid4().hex[:8]}"
        handle = WorkerHatchAttempt().run_hatch(
            placeholder_id=placeholder_id,
            spore_id=spore_id,
            spore_config=spore_config,
            task_prompt=task_prompt,
            eu_budget=eu_budget,
            soul_context=soul_context,
            workers=self._pool.all_handles(),
            lock=RLock(),
            ensure_result_collector=self._ensure_result_collector,
            ensure_watchdog=self._watchdog_lifecycle.start,
            hatch_worker=lambda config, prompt, budget, context: self._hatcher.hatch(
                config,
                prompt,
                budget,
                soul_context=context,
            ),
            logger=logger,
        )

        # Finalise: register in pool
        is_thread_worker = spore_config.get("handler_type") == "internal_thread"
        self._pool.register(handle, is_thread_worker=is_thread_worker)
        if self._persistence.is_available:
            self._persistence.save_worker(handle)

        # Start watchdog and register worker
        self._watchdog_lifecycle.start()
        self._watchdog_lifecycle.watch(handle)

        logger.info(
            "[SwarmLifecycleManager] Spawned worker='%s' spore='%s' pid=%d",
            handle.worker_id,
            spore_id,
            handle.pid,
        )
        self._events.emit(
            "worker.spawned",
            {"worker_id": handle.worker_id, "spore_id": spore_id, "pid": handle.pid},
        )
        self._store_agent_metadata(handle.worker_id, spore_id, handle.pid)

        return handle

    def _store_agent_metadata_via_bos(self, worker_id: str, spore_id: str, pid: int) -> None:
        """Persist spawned-worker metadata via bos://D-Memory/store."""
        self._store_agent_metadata(worker_id, spore_id, pid)

    def _store_agent_metadata(self, worker_id: str, spore_id: str, pid: int) -> None:
        """Persist spawned-worker metadata via bos://D-Memory/store."""
        import importlib as _il

        try:
            _mem = _il.import_module("organs.D_Memory.organs.unified_memory_api")
            _get_default_api = _mem.get_default_unified_memory_api
        except (ImportError, ModuleNotFoundError, AttributeError) as exc:
            logger.debug(
                "[SwarmLifecycleManager] UnifiedMemoryAPI unavailable: %s",
                exc,
            )
            return

        import asyncio as _asyncio
        import json as _json

        key = f"bos://D-Memory/agent/{worker_id}/metadata"
        value = _json.dumps({"worker_id": worker_id, "spore_id": spore_id, "pid": pid})

        try:
            api = _get_default_api()
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug(
                "[SwarmLifecycleManager] metadata persistence skipped: %s",
                exc,
            )
            return

        try:
            loop = _asyncio.get_running_loop()
        except RuntimeError:
            try:
                _asyncio.run(api.store(key=key, value=value, importance=0.3, ttl=3600.0))
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                logger.debug(
                    "[SwarmLifecycleManager] metadata persistence skipped: %s",
                    exc,
                )
            return

        try:
            loop.create_task(api.store(key=key, value=value, importance=0.3, ttl=3600.0))  # noqa: RUF006
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug(
                "[SwarmLifecycleManager] metadata persistence skipped: %s",
                exc,
            )

    def _on_state_change_proxy(
        self,
        worker_id: str,
        old_state: str,
        new_state: str,
    ) -> None:
        """Proxy state changes from the state machine back to pool heartbeat."""
        if new_state == "ACTIVE":
            self._pool.ping_heartbeat(worker_id)

    def _synapse_unregister(self, worker_id: str) -> None:
        """Unregister worker from SynapseRegistry if it was registered there."""
        if self._synapse_registry is None:
            return
        try:
            self._synapse_registry.unregister(worker_id)
        except (TypeError, ValueError, AttributeError) as exc:
            logger.debug(
                "[SwarmLifecycleManager] SynapseRegistry unregister skipped for '%s': %s",
                worker_id,
                exc,
            )

    # ─── CoreService.call dispatch (delegated to CallDispatcher) ────────────

    def call(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Override CoreService.call to delegate to CallDispatcher."""
        return self._dispatcher.dispatch(action, params)

    def _handle_governance_action(self, params: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible dispatcher entrypoint for governance actions."""
        return self._dispatcher._handle_governance_action(params)

    def _emit_lifecycle_event(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Backward-compatible lifecycle event shim."""
        self._events.emit(event_type, payload)


# ──────────────────────────────────────────────────────────────────────────────
# Backward-compatibility re-exports from this package
# ──────────────────────────────────────────────────────────────────────────────
# Re-export exception classes from this module for external consumers
InvalidTransitionError = InvalidTransitionError
WorkerNotFoundError = WorkerNotFoundError

# ──────────────────────────────────────────────────────────────────────────────
# Auto-register soul context with PossessionManager
# ──────────────────────────────────────────────────────────────────────────────
try:
    __import__("organs.D_Gateway.organs.possession_manager")
    _log.debug(
        "[SwarmLifecycleManager] PossessionManager callback registration available — "
        "call register_soul_context_callback(instance.set_soul_context) after construction."
    )
    _POSSESSION_MANAGER_AVAILABLE = True
except ImportError:
    _POSSESSION_MANAGER_AVAILABLE = False
