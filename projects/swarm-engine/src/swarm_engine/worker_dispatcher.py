from __future__ import annotations

from ._compat import bos_agent_router_bridge, get_synapse_registry

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
# Worker Dispatcher ≡ Worker
# 内涵 ≝ {Worker, Dispatcher}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, WorkerDispatcher)}
# 功能 ⊢ {Worker_Dispatcher, Init_Worker, Validate_Dispatcher}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import asyncio
import copy
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import uuid4

_log = logging.getLogger(__name__)
logger = logging.getLogger("bos.arterial_orchestrator")

if TYPE_CHECKING:
    from .organs.engine.possession_multi_session import (  # type: ignore[import-not-found]
        PossessionMultiSession,
    )
    from .organs.engine.result_bus import ResultBus
    from .organs.voice_session_particle_queue import QueuedSessionParticle  # type: ignore[import-not-found]

try:
    from nucleus.Z_Spore.interfaces.structured_error import (  # type: ignore[import-not-found]
        ErrorCatalog as _ErrorCatalog,
    )

    _STRUCTURED_ERRORS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _STRUCTURED_ERRORS_AVAILABLE = False


class WorkerDispatcher:
    """Worker dispatch, swarm lifecycle, and result aggregation."""

    _DEGRADED_EU_BUDGET_CAP = 0.5

    def __init__(
        self,
        store: Any,
        registry: Any,
        semantic_orchestrator: Any | None = None,
        session_particle_queue: Any | None = None,
    ) -> None:
        self._store = store
        self._registry = registry
        self._semantic_orchestrator = semantic_orchestrator
        self._swarm_manager: Any | None = None
        self._swarm_lock = threading.Lock()
        self._session_particle_queue = session_particle_queue

    def recruit_symphony_master(self, vision_id: str) -> str | None:
        if self._semantic_orchestrator and hasattr(self._semantic_orchestrator, "_matcher"):
            try:
                master = self._semantic_orchestrator._matcher.match_from_registry("symphony_master,coordination")
                if master:
                    logger.info(f"🎭 [Orchestrator] Recruited Symphony Master: {master.worker_id} for {vision_id}")
                    return str(master.worker_id)
            except (ImportError, ModuleNotFoundError, TypeError, ValueError, AttributeError) as e:
                logger.error(f"⚠️ [Orchestrator] Failed to recruit Master: {e}")
        logger.warning("⚠️ [Orchestrator] No virtual Master found, using System Proxy.")
        return "W-SYSTEM-PROXY"

    def resolve_target(self, task_id: str, capability: str) -> str | None:
        from .organs.engine.capability_registry import TaskRequest  # type: ignore[import-not-found]

        if self._registry is not None:
            try:
                req = TaskRequest(task_id=task_id, required_capabilities=[capability], priority=5)
                target = self._registry.find_best_agent(req)
                if target:
                    return str(target)
            except sqlite3.Error as exc:
                _log.debug("CapabilityRegistry lookup failed: %s", exc)
        try:
            worker = get_synapse_registry().select_for_task(
                task_type=capability, eu_budget=50.0, required_capabilities=[capability]
            )
            if worker:
                return str(worker.synapse_id)
        except ImportError:
            _log.debug("SynapseRegistry not available for dispatch fallback")
        except (RuntimeError, OSError, ValueError) as exc:
            _log.warning("SynapseRegistry query failed: %s", exc)
        return None

    def _build_handoff_payload(
        self,
        entry: QueuedSessionParticle,
        *,
        possession_session_manager: PossessionMultiSession | None = None,
    ) -> dict[str, Any]:
        handoff_payload: dict[str, Any] = {
            "session_id": entry.session_id,
            "source_surface": entry.source_surface,
            "continuity_context": dict(entry.continuity_context),
        }
        context_snapshot = getattr(entry.particle, "context_snapshot", {})
        if isinstance(context_snapshot, dict) and context_snapshot:
            handoff_payload["context_snapshot"] = dict(context_snapshot)

        controller_session_id = str(entry.continuity_context.get("controller_session_id", "")).strip()
        if possession_session_manager is None or not controller_session_id:
            return handoff_payload

        worker_sessions = possession_session_manager.get_worker_sessions(controller_session_id)
        worker_session_ids = [session.session_id for session in worker_sessions]
        handoff_payload["controller_session_id"] = controller_session_id
        handoff_payload["worker_cohort_session_ids"] = worker_session_ids
        handoff_payload["worker_cohort_size"] = len(worker_session_ids)
        return handoff_payload

    def _bootstrap_handoff_task_record(
        self,
        tid: str,
        summary: str,
        cap: str,
        *,
        handoff_context: dict[str, Any] | None = None,
    ) -> None:
        store_get = getattr(self._store, "get", None)
        store_save = getattr(self._store, "save", None)
        if not callable(store_get) or not callable(store_save):
            return
        if store_get(tid) is not None:
            return

        from .organs.engine.task_store import TaskRecord, TaskState  # type: ignore[import-not-found]

        source_surface = str(handoff_context.get("source_surface", "")).strip() if handoff_context else ""
        task_type = f"{source_surface}_handoff" if source_surface else "session_handoff"
        record = TaskRecord(
            task_id=tid,
            intent=summary,
            state=TaskState.pending,
            role_id=cap,
            task_type=task_type,
        )
        store_save(record)

    def get_task_snapshot(self, task_id: str) -> dict[str, Any] | None:
        store_get = getattr(self._store, "get", None)
        if not callable(store_get):
            return None
        record = store_get(task_id)
        if record is None:
            return None
        return {
            "task_id": record.task_id,
            "state": record.state.value,
            "worker_id": record.worker_id,
            "role_id": record.role_id,
            "task_type": record.task_type,
        }

    async def send_single_task(
        self,
        tid: str,
        summary: str,
        cap: str,
        handoff_context: dict[str, Any] | None = None,
    ) -> bool:
        from .organs.engine.task_store import TaskState

        if handoff_context is not None:
            self._bootstrap_handoff_task_record(
                tid,
                summary,
                cap,
                handoff_context=handoff_context,
            )
        target = self.resolve_target(tid, cap)
        if target:
            _log.info("📡 [Orchestrator] 发射物理任务: %s → %s (tid=%s)", summary, target, tid)
            from ._compat import MessageEnvelope

            payload: dict[str, Any] = {"task_id": tid, "summary": summary, "action": "execute"}
            if handoff_context:
                payload["handoff"] = copy.deepcopy(handoff_context)
            envelope = MessageEnvelope(
                source="Orchestrator",
                target=target,
                type="COMMAND",
                payload=payload,
                eu_budget=50.0,
            )
            _log.debug("📡 [Orchestrator] Calling agent_send_envelope for %s", tid)
            msg_id = await asyncio.get_running_loop().run_in_executor(
                None, bos_agent_router_bridge.agent_send_envelope, envelope
            )
            if msg_id:
                _log.info("📡 [Orchestrator] Message sent OK. ID: %s", msg_id)
                self._store.transition(tid, TaskState.running, worker_id=target)
                return True
            else:
                _log.warning("📡 [Orchestrator] agent_send_envelope returned None for %s", tid)
        else:
            _log.warning("📡 [Orchestrator] No target resolved for task %s (cap=%s)", tid, cap)
        return False

    def record_execution_outcome(
        self,
        task_id: str,
        *,
        result: Any | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        from .organs.engine.task_store import TaskState

        if not hasattr(self._store, "transition") or not hasattr(self._store, "get"):
            raise RuntimeError("task store unavailable for execution outcome")

        if error:
            self._store.transition(task_id, TaskState.failed, error=str(error))
        else:
            if result is None:
                serialized_result = ""
            elif isinstance(result, str):
                serialized_result = result
            else:
                serialized_result = json.dumps(result, sort_keys=True)
            self._store.transition(task_id, TaskState.completed, result=serialized_result)

        record = self._store.get(task_id)
        if record is None:
            raise KeyError(f"TaskStore: unknown task_id={task_id!r}")
        return {
            "task_id": record.task_id,
            "state": record.state.value,
            "result": record.result,
            "error": record.error,
            "worker_id": record.worker_id,
            "task_type": record.task_type,
        }

    def consume_task_results(self, worker_id: str, *, task_id: str | None = None) -> list[dict[str, Any]]:
        from .organs.engine.result_bus import ResultBus  # type: ignore[import-not-found]

        bus = ResultBus.get_instance()
        drained = bus.drain_task_results(worker_id, task_id) if task_id is not None else bus.drain_results(worker_id)
        outcomes: list[dict[str, Any]] = []
        for result in drained:
            result_task_id = str(getattr(result, "task_id", "")).strip()
            if not result_task_id:
                continue

            bus_result = {
                "output": str(getattr(result, "output", "")),
                "eu_consumed": float(getattr(result, "eu_consumed", 0.0)),
                "duration_s": float(getattr(result, "duration_s", 0.0)),
                "quality_score": float(getattr(result, "quality_score", 0.0)),
                "worker_id": str(getattr(result, "worker_id", "")),
                "control_plane": str(getattr(result, "control_plane", "")),
                "controller_session_id": str(getattr(result, "controller_session_id", "")),
                "controller_node_id": str(getattr(result, "controller_node_id", "")),
                "orchestration_id": str(getattr(result, "orchestration_id", "")),
                "orchestration_target": str(getattr(result, "orchestration_target", "")),
                "orchestration_goal": str(getattr(result, "orchestration_goal", "")),
            }
            success = bool(getattr(result, "success", False))
            outcome = self.record_execution_outcome(
                result_task_id,
                result=bus_result if success else None,
                error=str(getattr(result, "error", "")) if not success else None,
            )
            outcome["success"] = success
            outcome["bus_result"] = bus_result
            outcomes.append(outcome)
        return outcomes

    async def dispatch_tasks(self, vision_id: str) -> None:
        try:
            tasks = self._store.fetch_all(
                "SELECT task_id, intent, role_id FROM task_records "
                "WHERE parent_id=? OR parent_id IN "
                "(SELECT task_id FROM task_records WHERE parent_id=?)",
                (vision_id, vision_id),
            )
        except sqlite3.Error:
            tasks = []
        if not tasks:
            return
        # Batch dispatch to avoid rate limit hammering
        BATCH_SIZE = 50  # noqa: N806
        sent_ok = 0
        for i in range(0, len(tasks), BATCH_SIZE):
            batch = tasks[i : i + BATCH_SIZE]
            coros = [self.send_single_task(t["task_id"], t["intent"], t["role_id"]) for t in batch]
            results = await asyncio.gather(*coros)
            sent_ok += sum(1 for r in results if r)
            await asyncio.sleep(1.0)  # breathe between batches
        _log.info(
            "✅ [Orchestrator] Successfully dispatched %d/%d tasks.",
            sent_ok,
            len(tasks),
        )

    async def dispatch_queued_particles(
        self,
        session_id: str,
        *,
        possession_session_manager: PossessionMultiSession | None = None,
    ) -> dict[str, Any]:
        """Dispatch queued voice particles for a session without polling the DB."""
        if self._session_particle_queue is None:
            try:
                from .organs.voice_session_particle_queue import (
                    get_default_voice_session_particle_queue,
                )

                self._session_particle_queue = get_default_voice_session_particle_queue()
            except ImportError:
                return {
                    "session_id": session_id,
                    "dispatched": 0,
                    "failed": 0,
                    "pending": 0,
                    "error": "voice session particle queue unavailable",
                    "cohort_bindings": {},
                    "topology_failures": {},
                    "task_workers": {},
                }

        queued = self._session_particle_queue.peek_particles_for_session(session_id)
        if not queued:
            return {
                "session_id": session_id,
                "dispatched": 0,
                "failed": 0,
                "pending": 0,
                "cohort_bindings": {},
                "topology_failures": {},
                "task_workers": {},
            }

        dispatched = 0
        failed = 0
        failed_ids: list[str] = []
        dispatched_ids: list[str] = []
        cohort_bindings: dict[str, list[str]] = {}
        topology_failures: dict[str, str] = {}
        task_workers: dict[str, str] = {}

        for entry in queued:
            capability = entry.particle.required_capabilities[0] if entry.particle.required_capabilities else "*"
            try:
                handoff_payload = self._build_handoff_payload(
                    entry, possession_session_manager=possession_session_manager
                )
            except KeyError as exc:
                _log.warning(
                    "Queued particle %s topology resolution failed: %s",
                    entry.particle_id,
                    exc,
                )
                failed += 1
                failed_ids.append(entry.particle_id)
                topology_failures[entry.particle_id] = str(exc)
                continue

            worker_cohort_session_ids = handoff_payload.get("worker_cohort_session_ids")
            if isinstance(worker_cohort_session_ids, list):
                cohort_bindings[entry.particle_id] = list(worker_cohort_session_ids)

            sent = await self.send_single_task(
                entry.particle.id,
                entry.particle.intent,
                capability,
                handoff_context=handoff_payload,
            )
            if sent:
                self._session_particle_queue.remove_particle(session_id, entry.particle_id)
                dispatched += 1
                dispatched_ids.append(entry.particle_id)
                snapshot = self.get_task_snapshot(entry.particle_id)
                if snapshot is not None and str(snapshot.get("worker_id", "")).strip():
                    task_workers[entry.particle_id] = str(snapshot["worker_id"])
            else:
                failed += 1
                failed_ids.append(entry.particle_id)

        return {
            "session_id": session_id,
            "dispatched": dispatched,
            "failed": failed,
            "pending": self._session_particle_queue.size(session_id),
            "dispatched_ids": dispatched_ids,
            "failed_ids": failed_ids,
            "cohort_bindings": cohort_bindings,
            "topology_failures": topology_failures,
            "task_workers": task_workers,
        }

    def get_swarm_manager(self) -> Any:
        from .organs.agent_orchestrator import SwarmDispatchError  # type: ignore[import-not-found]

        with self._swarm_lock:
            if self._swarm_manager is None:
                try:
                    from .organs.swarm_lifecycle_manager import (  # type: ignore[import-not-found]
                        SwarmLifecycleManager as SwarmLifecycleManagerClass,
                    )

                    self._swarm_manager = SwarmLifecycleManagerClass()
                    logger.info("[Orchestrator] SwarmLifecycleManager initialised.")
                except Exception as exc:
                    raise SwarmDispatchError(f"[Orchestrator] SwarmLifecycleManager unavailable: {exc}") from exc
        return self._swarm_manager

    def build_swarm_soul_context(
        self,
        task_prompt: str,
        capability: str,
        eu_budget: float,
        soul_context: Mapping[str, object] | None = None,
    ) -> dict[str, object] | None:
        """Return a dispatch-ready soul context enriched with orchestration hints."""
        if soul_context is None:
            return None

        enriched = copy.deepcopy(dict(soul_context))
        raw_orchestration = enriched.get("orchestration", {})
        if raw_orchestration is None:
            raw_orchestration = {}
        if not isinstance(raw_orchestration, Mapping):
            raise TypeError("soul_context['orchestration'] must be a mapping when provided")
        orchestration = dict(raw_orchestration)
        orchestration.setdefault("orchestration_id", f"orch-{uuid4().hex[:10]}")
        orchestration.setdefault("goal", task_prompt)
        orchestration.setdefault("target", capability)
        orchestration.setdefault(
            "input_payload",
            {
                "dispatch_capability": capability,
                "dispatch_eu_budget": eu_budget,
            },
        )
        enriched["orchestration"] = orchestration
        return enriched

    def enforce_governance_on_dispatch(
        self,
        *,
        capability: str,
        eu_budget: float,
        soul_context: Mapping[str, object] | None,
    ) -> tuple[float, Mapping[str, object] | None]:
        """Apply minimal runtime governance before spawning a swarm worker."""
        if soul_context is None:
            return eu_budget, soul_context

        status = str(soul_context.get("governance_status", "")).strip().upper()
        if status in {"FROZEN", "RECLAIMED"}:
            raise RuntimeError(f"Dispatch blocked by governance status {status} for capability '{capability}'")

        if status != "DEGRADED":
            return eu_budget, soul_context

        enforced_budget = min(eu_budget, self._DEGRADED_EU_BUDGET_CAP)
        if enforced_budget == eu_budget:
            return eu_budget, soul_context

        downgraded_context = copy.deepcopy(dict(soul_context))
        governance_history = downgraded_context.get("governance_history", [])
        if governance_history is None:
            governance_history = []
        if not isinstance(governance_history, list):
            raise TypeError("soul_context['governance_history'] must be a list when provided")
        governance_history.append(
            {
                "action": "DOWNGRADE",
                "actor_id": "worker-dispatcher",
                "reason": (
                    f"dispatch runtime capped to {self._DEGRADED_EU_BUDGET_CAP:.1f} EU under DEGRADED governance"
                ),
            }
        )
        downgraded_context["governance_history"] = governance_history
        return enforced_budget, downgraded_context

    def apply_orchestration_metadata_to_handle(
        self, handle: Any, soul_context: Mapping[str, object] | None = None
    ) -> Any:
        """Project orchestration metadata from soul_context onto a WorkerHandle."""
        if soul_context is None:
            return handle

        orchestration = soul_context.get("orchestration", {})
        if isinstance(orchestration, dict):
            handle.orchestration_id = str(orchestration.get("orchestration_id", ""))
            handle.orchestration_target = str(orchestration.get("target", ""))
            handle.orchestration_goal = str(orchestration.get("goal", ""))
        control_plane = str(
            soul_context.get(
                "control_plane",
                "cockpit" if soul_context.get("cockpit_mode") else "",
            )
        )
        if control_plane:
            handle.control_plane = control_plane
            handle.controller_session_id = str(
                soul_context.get("controller_session_id", soul_context.get("session_id", ""))
            )
            handle.controller_node_id = str(soul_context.get("controller_node_id", soul_context.get("node_id", "")))
        return handle

    def project_handle_metadata(self, source: Any, target: Any) -> Any:
        """Copy orchestration metadata from a handle-like object onto another object."""
        for attr in (
            "orchestration_id",
            "orchestration_target",
            "orchestration_goal",
            "control_plane",
            "controller_session_id",
            "controller_node_id",
        ):
            value = getattr(source, attr, "")
            if value:
                setattr(target, attr, value)
        return target

    def build_orchestration_metadata_map(self, handles: list[Any]) -> dict[str, dict[str, str]]:
        """Build a per-worker orchestration metadata map for reports and audit surfaces."""
        metadata: dict[str, dict[str, str]] = {}
        for handle in handles:
            worker_id = getattr(handle, "worker_id", "")
            if not worker_id:
                continue
            values = {
                "orchestration_id": getattr(handle, "orchestration_id", ""),
                "orchestration_target": getattr(handle, "orchestration_target", ""),
                "orchestration_goal": getattr(handle, "orchestration_goal", ""),
                "control_plane": getattr(handle, "control_plane", ""),
                "controller_session_id": getattr(handle, "controller_session_id", ""),
                "controller_node_id": getattr(handle, "controller_node_id", ""),
            }
            filtered = {k: v for k, v in values.items() if v}
            if filtered:
                metadata[worker_id] = filtered
        return metadata

    def dispatch_to_swarm(
        self,
        task_prompt: str,
        capability: str = "*",
        eu_budget: float = 1.0,
        soul_context: Mapping[str, object] | None = None,
    ) -> Any:
        from .organs.agent_orchestrator import SwarmDispatchError

        try:
            swarm = self.get_swarm_manager()
        except SwarmDispatchError:
            raise
        try:
            effective_budget, effective_soul_context = self.enforce_governance_on_dispatch(
                capability=capability,
                eu_budget=eu_budget,
                soul_context=soul_context,
            )
            enriched_soul_context = self.build_swarm_soul_context(
                task_prompt,
                capability,
                effective_budget,
                soul_context=effective_soul_context,
            )
            if soul_context is None:
                handle = swarm.spawn(capability, effective_budget, task_prompt)
            else:
                handle = swarm.spawn(
                    capability,
                    effective_budget,
                    task_prompt,
                    soul_context=enriched_soul_context,
                )
                handle = self.apply_orchestration_metadata_to_handle(
                    handle,
                    soul_context=enriched_soul_context,
                )
            logger.info(
                "[Orchestrator] Dispatched to swarm: worker='%s' capability='%s'",
                handle.worker_id,
                capability,
            )
            return handle
        except Exception as exc:
            raise SwarmDispatchError(
                f"[Orchestrator] Swarm dispatch failed (capability='{capability}'): {exc}"
            ) from exc

    def get_swarm_results(self, worker_id: str) -> Any | None:
        if self._swarm_manager is None:
            return None
        try:
            from nucleus.Z_Spore.interfaces.swarm import WorkerBundle, WorkerState  # type: ignore[import-not-found]

            handle = self._swarm_manager.get_handle(worker_id)
            if handle.state in (WorkerState.REAPED, WorkerState.CRYSTALLIZING):
                task_results = list(getattr(handle, "_task_results", []))
                total_eu = sum(r.eu_consumed for r in task_results)
                bundle = WorkerBundle(
                    handle=handle,
                    task_results=task_results,
                    total_eu_consumed=total_eu,
                    total_tasks=len(task_results),
                    successful_tasks=sum(1 for r in task_results if r.success),
                )
                bundle = self.project_handle_metadata(handle, bundle)
                return bundle
            return None
        except (ImportError, KeyError, AttributeError):
            return None

    def wait_for_swarm(self, worker_id: str, timeout_s: float = 30.0) -> Any:
        result_bus_class: type[ResultBus] | None = None
        try:
            try:
                from .organs.engine.result_bus import ResultBus as ResultBusClass
            except ImportError:
                from engine.result_bus import ResultBus as ResultBusClass  # type: ignore[import-not-found]
            result_bus_class = ResultBusClass
        except ImportError:
            result_bus_class = None
        deadline = time.monotonic() + timeout_s
        accumulated_extra: list[object] = []
        while time.monotonic() < deadline:
            if result_bus_class is not None:
                try:
                    accumulated_extra.extend(result_bus_class.get_instance().drain_results(worker_id))
                except (sqlite3.Error, OSError, ValueError) as e:
                    _log.warning("cleanup failed: %s", e)
            bundle = self.get_swarm_results(worker_id)
            if bundle is not None:
                if accumulated_extra:
                    existing_ids = {r.task_id for r in bundle.task_results}
                    for r in accumulated_extra:
                        if r.task_id not in existing_ids:
                            bundle.task_results.append(r)
                            bundle.total_tasks += 1
                            bundle.total_eu_consumed += r.eu_consumed
                            if r.success:
                                bundle.successful_tasks += 1
                logger.info(
                    "[Orchestrator] Worker '%s' completed: tasks=%d eu=%.2f",
                    worker_id,
                    bundle.total_tasks,
                    bundle.total_eu_consumed,
                )
                return bundle
            time.sleep(0.5)
        if _STRUCTURED_ERRORS_AVAILABLE:
            raise _ErrorCatalog.task_timeout(worker_id, timeout_s=timeout_s)
        raise TimeoutError(f"[Orchestrator] Swarm worker '{worker_id}' did not complete within {timeout_s:.1f}s.")

    def aggregate_results(self, worker_ids: list[str], task_id: str = "") -> Any:
        try:
            try:
                from .organs.result_aggregator import ResultAggregator  # type: ignore[import-not-found]
            except ImportError:
                from result_aggregator import ResultAggregator  # type: ignore[no-redef, import-not-found]
        except ImportError as exc:
            logger.error("[Orchestrator] ResultAggregator not available: %s", exc)
            raise
        result_bus_class: type[ResultBus] | None = None
        try:
            try:
                from .organs.engine.result_bus import ResultBus as ResultBusClass
            except ImportError:
                from engine.result_bus import ResultBus as ResultBusClass
            result_bus_class = ResultBusClass
        except ImportError:
            result_bus_class = None
        all_results: list[Any] = []
        handles: list[Any] = []
        for wid in worker_ids:
            if result_bus_class is not None:
                try:
                    all_results.extend(result_bus_class.get_instance().drain_results(wid))
                except (sqlite3.Error, OSError, ValueError) as e:
                    _log.warning("agent shutdown failed: %s", e)
            if self._swarm_manager is not None:
                try:
                    handle = self._swarm_manager.get_handle(wid)
                    handles.append(handle)
                    handle_results = list(getattr(handle, "_task_results", []))
                    existing_ids = {getattr(r, "task_id", None) for r in all_results}
                    for r in handle_results:
                        if getattr(r, "task_id", None) not in existing_ids:
                            all_results.append(r)
                except (KeyError, AttributeError) as e:
                    _log.warning("agent cleanup failed: %s", e)
        aggregator = ResultAggregator()
        report = aggregator.aggregate(all_results, task_id=task_id)
        report.orchestration_metadata = self.build_orchestration_metadata_map(handles)
        report.markdown_report = aggregator.to_markdown(report)
        logger.info(
            "[Orchestrator] Aggregated %d results for %d workers — success=%.1f%% eu=%.2f",
            len(all_results),
            len(worker_ids),
            report.success_rate * 100,
            report.eu_consumed,
        )
        return report
