# ---
# domain: D-Execution
# layer: organ
# status: active
# ---
from __future__ import annotations

import importlib
import json
import sqlite3
from collections.abc import Callable
from typing import Any


class ExecutionCompatHelper:
    """Plain helper for RFC-026 compatibility reads and swarm governance shims."""

    def __init__(
        self,
        agent_orchestrator: Any,
        get_execution_log: Callable[[int], list[dict[str, Any]]],
        get_execution_log_size: Callable[[], int],
    ) -> None:
        self._agent_orchestrator = agent_orchestrator
        self._get_execution_log = get_execution_log
        self._get_execution_log_size = get_execution_log_size

    def log_tail(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._get_execution_log(limit)

    def log_size(self) -> int:
        return self._get_execution_log_size()

    def _phase_for_status(self, status: str | None) -> str:
        status_norm = (status or "").upper()
        if status_norm in {"PENDING", "NEW"}:
            return "Anchoring"
        if status_norm in {"ACTIVE", "RUNNING", "IN_PROGRESS"}:
            return "Implementation"
        if status_norm in {"DONE", "COMPLETED"}:
            return "Polishing"
        if status_norm in {"FAILED", "ERROR", "CANCELLED"}:
            return "Failed"
        return "Queued"

    def _progress_for_status(self, status: str | None) -> int:
        status_norm = (status or "").upper()
        if status_norm in {"PENDING", "NEW"}:
            return 0
        if status_norm == "DECOMPOSED":
            return 25
        if status_norm in {"ACTIVE", "RUNNING", "IN_PROGRESS"}:
            return 50
        if status_norm in {"DONE", "COMPLETED"}:
            return 100
        if status_norm in {"FAILED", "ERROR", "CANCELLED"}:
            return 100
        return 0

    def task_list(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        store = getattr(self._agent_orchestrator, "_store", None)
        if store:
            try:
                fetched = store.fetch_all(
                    "SELECT task_id, intent, state, created_at FROM task_records ORDER BY created_at DESC LIMIT 50"
                )
                for row in fetched:
                    status = row["state"].upper()
                    rows.append(
                        {
                            "task_id": row["task_id"],
                            "status": status,
                            "phase": self._phase_for_status(status),
                            "progress": self._progress_for_status(status),
                            "intent": row["intent"],
                        }
                    )
            except (sqlite3.Error, KeyError, AttributeError, OSError):
                pass
        return {"status": "success", "data": rows}

    def task_status(self, params: dict[str, Any] | None) -> dict[str, Any]:
        task_id = (params or {}).get("task_id")
        if not task_id:
            return {"status": "error", "message": "task_id is required"}
        store = getattr(self._agent_orchestrator, "_store", None)
        if not store:
            return {"status": "error", "message": "Task store unavailable"}
        record = store.get(task_id)
        if record:
            record_state = getattr(record, "state", "")
            status = record_state.value.upper() if hasattr(record_state, "value") else str(record_state).upper()
            return {
                "status": "success",
                "data": {
                    "task_id": record.task_id,
                    "intent": record.intent,
                    "phase": self._phase_for_status(status),
                    "progress": self._progress_for_status(status),
                    "assigned_worker": record.worker_id or "Unassigned",
                    "status_text": status,
                    "journey_id": str(record.metadata.get("journey_id", "") or ""),
                    "journey_display_name": str(record.metadata.get("journey_display_name", "") or ""),
                },
            }
        return {"status": "error", "message": f"Task '{task_id}' not found"}

    def results_list(self) -> dict[str, Any]:
        db_path = getattr(self._agent_orchestrator, "db_path", None)
        if db_path:
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT task_id, worker_id, success, output, eu_consumed, "
                    "duration_s, quality_score, error FROM task_results "
                    "ORDER BY created_at DESC, id DESC LIMIT 50"
                ).fetchall()
                task_ids = [str(row["task_id"]) for row in rows if row["task_id"]]
                metadata_by_task = self._load_task_metadata(conn, task_ids)
                conn.close()
                return {
                    "status": "success",
                    "data": [self._result_row_with_metadata(row, metadata_by_task) for row in rows],
                }
            except (sqlite3.Error, KeyError, AttributeError, OSError):
                pass
        try:
            from .result_bus import ResultBus  # type: ignore[import-not-found]

            results = ResultBus.get_instance().list_results()
        except (ImportError, AttributeError, TypeError, ValueError):
            results = []
        return {"status": "success", "data": results}

    def _load_task_metadata(self, conn: sqlite3.Connection, task_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" for _ in task_ids)
        rows = conn.execute(
            f"SELECT task_id, metadata FROM task_records WHERE task_id IN ({placeholders})",  # noqa: S608
            tuple(task_ids),
        ).fetchall()
        metadata_by_task: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                metadata_by_task[str(row["task_id"])] = json.loads(row["metadata"] or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                metadata_by_task[str(row["task_id"])] = {}
        return metadata_by_task

    def _result_row_with_metadata(
        self,
        row: sqlite3.Row,
        metadata_by_task: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        result = {
            "task_id": row["task_id"],
            "worker_id": row["worker_id"],
            "success": bool(row["success"]),
            "output": row["output"],
            "eu_consumed": float(row["eu_consumed"]),
            "duration_s": float(row["duration_s"]),
            "quality_score": float(row["quality_score"]),
            "error": row["error"],
        }
        metadata = metadata_by_task.get(str(row["task_id"]), {})
        journey_id = str(metadata.get("journey_id", "") or "")
        journey_display_name = str(metadata.get("journey_display_name", "") or "")
        if journey_id:
            result["journey_id"] = journey_id
        if journey_display_name:
            result["journey_display_name"] = journey_display_name
        return result

    def swarm_radar(self) -> dict[str, Any]:
        data: list[dict[str, Any]] = []
        swarm = getattr(self._agent_orchestrator, "_swarm_manager", None)
        if swarm is None:
            try:
                daemon_swarm = importlib.import_module("nucleus.Z_Microkernel.infrastructure.bos_daemon.swarm")
                swarm = daemon_swarm.get_lifecycle_manager()
            except (ImportError, AttributeError, RuntimeError, OSError, TypeError, ValueError):
                swarm = None

        if swarm is not None and hasattr(swarm, "list_active"):
            try:
                handles = swarm.list_active()
                for handle in handles:
                    governance_history = list(getattr(handle, "governance_history", []))
                    last_event = (
                        governance_history[-1]
                        if governance_history and isinstance(governance_history[-1], dict)
                        else {}
                    )
                    data.append(
                        {
                            "worker_id": handle.worker_id,
                            "state": handle.state.value,
                            "eu_budget": float(getattr(handle, "eu_budget", 0.0)),
                            "eu_consumed": float(getattr(handle, "eu_consumed", 0.0)),
                            "capabilities": list(getattr(handle, "capabilities", [])),
                            "governance_status": str(getattr(handle, "governance_status", "") or "ACTIVE"),
                            "control_plane": str(getattr(handle, "control_plane", "")),
                            "controller_node_id": str(getattr(handle, "controller_node_id", "")),
                            "last_governance_action": str(last_event.get("action", "")),
                            "last_governance_reason": str(last_event.get("reason", "")),
                        }
                    )
            except (ValueError, TypeError, KeyError, AttributeError):
                pass

        if not data:
            try:
                from nucleus.Z_Microkernel.organs.capability_registry import (  # type: ignore[import-not-found]
                    CapabilityRegistry,
                )

                registry = CapabilityRegistry()
                for agent in registry.list_agents():
                    if isinstance(agent, dict):
                        data.append(
                            {
                                "worker_id": agent.get("agent_id", "unknown"),
                                "state": "ACTIVE",
                                "eu_budget": 20.0,
                                "eu_consumed": 0.0,
                                "capabilities": agent.get("capabilities", []),
                                "governance_status": "ACTIVE",
                                "control_plane": "",
                                "controller_node_id": "",
                                "last_governance_action": "",
                                "last_governance_reason": "",
                            }
                        )
            except ImportError:
                pass

        return {"status": "success", "data": data}

    def swarm_governance_action(self, params: dict[str, Any] | None) -> dict[str, Any]:
        payload = params or {}
        worker_id = str(payload.get("worker_id", "")).strip()
        task_id = str(payload.get("task_id", "")).strip()
        action = str(payload.get("action", "")).strip()
        actor_id = str(payload.get("actor_id", "")).strip()
        reason = str(payload.get("reason", "")).strip()

        if (not worker_id and not task_id) or not action or not actor_id or not reason:
            return {
                "status": "error",
                "message": "worker_id or task_id, action, actor_id, and reason are required",
            }

        swarm = getattr(self._agent_orchestrator, "_swarm_manager", None)
        if swarm is None:
            try:
                from nucleus.Z_Microkernel.infrastructure.bos_daemon.swarm import (  # type: ignore[import-not-found]
                    get_lifecycle_manager,
                )

                swarm = get_lifecycle_manager()
            except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
                swarm = None

        if swarm is None or not hasattr(swarm, "apply_governance_action"):
            return {"status": "error", "message": "SwarmLifecycleManager unavailable"}

        try:
            if task_id and not worker_id:
                task_worker_ids = [
                    str(record.get("worker_id", "")).strip()
                    for record in self.results_list().get("data", [])
                    if str(record.get("task_id", "")).strip() == task_id and str(record.get("worker_id", "")).strip()
                ]
                deduped_task_worker_ids = sorted(dict.fromkeys(task_worker_ids))
                active_worker_ids = {
                    str(getattr(handle, "worker_id", "")).strip()
                    for handle in getattr(swarm, "list_active", lambda: [])()
                    if str(getattr(handle, "worker_id", "")).strip()
                }
                active_task_worker_ids = [
                    candidate for candidate in deduped_task_worker_ids if candidate in active_worker_ids
                ]
                skipped_workers = [
                    candidate for candidate in deduped_task_worker_ids if candidate not in active_worker_ids
                ]
                if not active_task_worker_ids:
                    return {
                        "status": "error",
                        "message": f"No active workers found for task_id '{task_id}'",
                    }

                runtime_results = []
                failed_workers = []
                for runtime_worker_id in active_task_worker_ids:
                    try:
                        runtime_results.append(
                            swarm.apply_governance_action(
                                runtime_worker_id,
                                action=action,
                                actor_id=actor_id,
                                reason=reason,
                            )
                        )
                    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
                        failed_workers.append({"worker_id": runtime_worker_id, "message": str(exc)})
                successful_workers = [
                    str(item.get("worker_id", "")).strip()
                    for item in runtime_results
                    if str(item.get("worker_id", "")).strip()
                ]
                if not successful_workers:
                    return {
                        "status": "error",
                        "message": (f"Failed to apply governance action to active workers for task_id '{task_id}'"),
                    }
                partial_failure = bool(skipped_workers or failed_workers)
                last_success = runtime_results[-1]
                return {
                    "status": "success",
                    "data": {
                        "task_id": task_id,
                        "target_scope": "task",
                        "total_workers": len(deduped_task_worker_ids),
                        "affected_count": len(successful_workers),
                        "affected_workers": successful_workers,
                        "skipped_workers": skipped_workers,
                        "failed_workers": failed_workers,
                        "partial_failure": partial_failure,
                        "governance_status": last_success.get("governance_status", ""),
                        "runtime_effect": (
                            "partial_failure" if partial_failure else last_success.get("runtime_effect", "")
                        ),
                        "last_action": last_success.get("last_action", ""),
                        "last_reason": last_success.get("last_reason", ""),
                    },
                }

            result = swarm.apply_governance_action(
                worker_id,
                action=action,
                actor_id=actor_id,
                reason=reason,
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            return {"status": "error", "message": str(exc)}

        return {"status": "success", "data": result, "eu_consumed": 0.0}
