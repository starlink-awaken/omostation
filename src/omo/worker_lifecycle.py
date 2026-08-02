"""Durable worker acknowledgement and lease lifecycle for Workflow Mesh.

The dispatch YAML remains an operator-facing artifact. These functions make
the worker lifecycle durable by recording it in the same append-only event log
as admission, step progress, recovery, and evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .workflow_mesh import WorkflowMeshEventError, WorkflowMeshStore, new_workflow_event


class WorkerLifecycleError(ValueError):
    """A worker lifecycle transition failed its mesh contract."""


def _utc(value: str | None = None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _stamp(value: str | None = None) -> str:
    return _utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _store(omo_dir: Path | str) -> WorkflowMeshStore:
    return WorkflowMeshStore(omo_dir)


def _existing(store: WorkflowMeshStore, idempotency_key: str) -> dict[str, Any] | None:
    for event in store.events():
        if event.get("idempotency_key") == idempotency_key:
            return event
    return None


def _append(
    store: WorkflowMeshStore,
    event_type: str,
    workflow_run_id: str,
    *,
    trace_id: str,
    producer: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    prior = _existing(store, idempotency_key)
    if prior is not None:
        if prior.get("event_type") != event_type or prior.get("payload") != payload:
            raise WorkerLifecycleError(
                f"conflicting worker lifecycle event: {idempotency_key}"
            )
        return prior
    try:
        return store.append(
            new_workflow_event(
                event_type,
                workflow_run_id,
                trace_id=trace_id,
                producer=producer,
                idempotency_key=idempotency_key,
                payload=payload,
            )
        )
    except WorkflowMeshEventError as exc:
        raise WorkerLifecycleError(str(exc)) from exc


def _validate_context(
    store: WorkflowMeshStore,
    *,
    workflow_run_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
) -> dict[str, Any]:
    snapshot = store.snapshot(workflow_run_id)
    if snapshot.get("state") in {"unknown", "planned", "closed", "cancelled"}:
        raise WorkerLifecycleError(
            f"workflow is not dispatchable for worker lifecycle: {snapshot.get('state')}"
        )
    admission = snapshot.get("admission")
    if not isinstance(admission, dict) or admission.get("admission_id") != admission_id:
        raise WorkerLifecycleError("worker lifecycle admission_id mismatch")
    step = snapshot.get("step_runs", {}).get(step_run_id)
    if not isinstance(step, dict):
        raise WorkerLifecycleError(f"unknown admitted StepRun: {step_run_id}")
    if step.get("admission_id") != admission_id:
        raise WorkerLifecycleError("worker lifecycle StepRun admission mismatch")
    if not dispatch_id or not worker_id:
        raise WorkerLifecycleError("dispatch_id and worker_id are required")
    return snapshot


def record_step_dispatch(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    step_name: str = "execute",
) -> dict[str, Any]:
    """Persist the coordinator-to-worker dispatch edge exactly once."""
    store = _store(omo_dir)
    payload = {
        "dispatch_id": dispatch_id,
        "worker_id": worker_id,
        "step_run_id": step_run_id,
        "step_name": step_name,
        "admission_id": admission_id,
    }
    return _append(
        store,
        "StepDispatched",
        workflow_run_id,
        trace_id=trace_id,
        producer="omo.worker_lifecycle",
        idempotency_key=f"{workflow_run_id}:step-dispatched:{dispatch_id}",
        payload=payload,
    )


def acknowledge_worker(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    lease_seconds: int = 1200,
    now: str | None = None,
) -> dict[str, Any]:
    """Record a worker ACK and establish its first durable lease."""
    if lease_seconds <= 0:
        raise WorkerLifecycleError("lease_seconds must be positive")
    store = _store(omo_dir)
    event_key = f"{workflow_run_id}:worker-ack:{dispatch_id}"
    prior = _existing(store, event_key)
    if prior is not None:
        return prior
    _validate_context(
        store,
        workflow_run_id=workflow_run_id,
        dispatch_id=dispatch_id,
        worker_id=worker_id,
        step_run_id=step_run_id,
        admission_id=admission_id,
    )
    acknowledged_at = _stamp(now)
    lease_expires_at = _stamp(
        (_utc(now) + timedelta(seconds=lease_seconds)).isoformat()
    )
    payload = {
        "dispatch_id": dispatch_id,
        "worker_id": worker_id,
        "step_run_id": step_run_id,
        "admission_id": admission_id,
        "acknowledged_at": acknowledged_at,
        "lease_expires_at": lease_expires_at,
    }
    return _append(
        store,
        "WorkerAcknowledged",
        workflow_run_id,
        trace_id=trace_id,
        producer="worker",
        idempotency_key=event_key,
        payload=payload,
    )


def renew_worker_lease(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    lease_seconds: int = 1200,
    now: str | None = None,
    heartbeat_id: str | None = None,
) -> dict[str, Any]:
    """Renew a live lease; repeated heartbeat IDs are idempotent."""
    if lease_seconds <= 0:
        raise WorkerLifecycleError("lease_seconds must be positive")
    store = _store(omo_dir)
    heartbeat_at = _stamp(now)
    lease_expires_at = _stamp(
        (_utc(now) + timedelta(seconds=lease_seconds)).isoformat()
    )
    event_key = heartbeat_id or lease_expires_at
    idempotency_key = f"{workflow_run_id}:worker-heartbeat:{dispatch_id}:{event_key}"
    prior = _existing(store, idempotency_key)
    if prior is not None:
        return prior
    snapshot = _validate_context(
        store,
        workflow_run_id=workflow_run_id,
        dispatch_id=dispatch_id,
        worker_id=worker_id,
        step_run_id=step_run_id,
        admission_id=admission_id,
    )
    current = snapshot.get("worker")
    if not isinstance(current, dict) or current.get("state") not in {
        "acknowledged",
        "active",
    }:
        raise WorkerLifecycleError("worker must ACK before renewing its lease")
    if (
        current.get("dispatch_id") != dispatch_id
        or current.get("worker_id") != worker_id
    ):
        raise WorkerLifecycleError("worker lease owner mismatch")
    payload = {
        "dispatch_id": dispatch_id,
        "worker_id": worker_id,
        "step_run_id": step_run_id,
        "admission_id": admission_id,
        "heartbeat_id": event_key,
        "heartbeat_at": heartbeat_at,
        "lease_expires_at": lease_expires_at,
    }
    return _append(
        store,
        "WorkerLeaseRenewed",
        workflow_run_id,
        trace_id=trace_id,
        producer="worker",
        idempotency_key=idempotency_key,
        payload=payload,
    )


def expire_worker_lease(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    now: str | None = None,
    reason: str = "lease_expired",
) -> dict[str, Any]:
    """Mark an unresponsive worker unavailable only after its lease expires."""
    store = _store(omo_dir)
    event_key = f"{workflow_run_id}:worker-expired:{dispatch_id}"
    prior = _existing(store, event_key)
    if prior is not None:
        return prior
    snapshot = _validate_context(
        store,
        workflow_run_id=workflow_run_id,
        dispatch_id=dispatch_id,
        worker_id=worker_id,
        step_run_id=step_run_id,
        admission_id=admission_id,
    )
    current = snapshot.get("worker")
    if not isinstance(current, dict) or current.get("state") not in {
        "acknowledged",
        "active",
    }:
        raise WorkerLifecycleError("worker has no live lease to expire")
    if (
        current.get("dispatch_id") != dispatch_id
        or current.get("worker_id") != worker_id
    ):
        raise WorkerLifecycleError("worker lease owner mismatch")
    observed_at = _stamp(now)
    lease_expires_at = str(current.get("lease_expires_at", ""))
    if not lease_expires_at or _utc(observed_at) < _utc(lease_expires_at):
        raise WorkerLifecycleError("worker lease has not expired")
    payload = {
        "dispatch_id": dispatch_id,
        "worker_id": worker_id,
        "step_run_id": step_run_id,
        "admission_id": admission_id,
        "lease_expires_at": lease_expires_at,
        "expired_at": observed_at,
        "reason": reason,
    }
    return _append(
        store,
        "WorkerLeaseExpired",
        workflow_run_id,
        trace_id=trace_id,
        producer="omo.worker_lifecycle",
        idempotency_key=event_key,
        payload=payload,
    )


def reclaim_worker(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    successor_worker_id: str,
    successor_dispatch_id: str,
    now: str | None = None,
    reason: str = "lease_expired",
) -> dict[str, Any]:
    """Record coordinator reclaim and successor assignment after expiry."""
    if not successor_worker_id or not successor_dispatch_id:
        raise WorkerLifecycleError(
            "successor_worker_id and successor_dispatch_id are required"
        )
    store = _store(omo_dir)
    event_key = (
        f"{workflow_run_id}:worker-reclaim:{dispatch_id}:{successor_dispatch_id}"
    )
    prior = _existing(store, event_key)
    if prior is not None:
        return prior
    snapshot = _validate_context(
        store,
        workflow_run_id=workflow_run_id,
        dispatch_id=dispatch_id,
        worker_id=worker_id,
        step_run_id=step_run_id,
        admission_id=admission_id,
    )
    current = snapshot.get("worker")
    if not isinstance(current, dict) or current.get("state") != "lease_expired":
        raise WorkerLifecycleError("worker must be lease_expired before reclaim")
    payload = {
        "dispatch_id": dispatch_id,
        "worker_id": worker_id,
        "step_run_id": step_run_id,
        "admission_id": admission_id,
        "successor_worker_id": successor_worker_id,
        "successor_dispatch_id": successor_dispatch_id,
        "reclaimed_at": _stamp(now),
        "reason": reason,
    }
    return _append(
        store,
        "WorkerReclaimed",
        workflow_run_id,
        trace_id=trace_id,
        producer="omo.worker_lifecycle",
        idempotency_key=event_key,
        payload=payload,
    )


def scan_worker_leases(
    omo_dir: Path | str,
    *,
    now: str | None = None,
    apply: bool = False,
    reason: str = "lease_expired",
) -> dict[str, Any]:
    """Find expired Mesh leases and optionally persist expiry events.

    The default is deliberately read-only so an operator, cron job, or UI can
    inspect the result without changing workflow state. ``apply=True`` only
    appends ``WorkerLeaseExpired``; successor selection remains a separate
    coordinator decision through :func:`reclaim_worker`.
    """
    if not str(reason).strip():
        raise WorkerLifecycleError("watchdog expiry reason is required")

    store = _store(omo_dir)
    observed_at = _stamp(now)
    run_ids = sorted(
        {
            str(event.get("workflow_run_id"))
            for event in store.events()
            if str(event.get("workflow_run_id") or "").strip()
        }
    )
    due: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    worker_count = 0

    for workflow_run_id in run_ids:
        try:
            snapshot = store.snapshot(workflow_run_id)
        except (WorkflowMeshEventError, OSError, ValueError) as exc:
            errors.append({"workflow_run_id": workflow_run_id, "error": str(exc)})
            continue

        worker = snapshot.get("worker")
        if not isinstance(worker, dict):
            continue
        worker_count += 1
        state = str(worker.get("state") or "unknown")
        if state not in {"acknowledged", "active"}:
            continue

        lease_expires_at = str(worker.get("lease_expires_at") or "")
        if not lease_expires_at:
            errors.append(
                {
                    "workflow_run_id": workflow_run_id,
                    "error": "live worker has no lease_expires_at",
                }
            )
            continue
        try:
            expired_now = _utc(observed_at) >= _utc(lease_expires_at)
        except ValueError as exc:
            errors.append({"workflow_run_id": workflow_run_id, "error": str(exc)})
            continue
        if not expired_now:
            continue

        context = {
            "workflow_run_id": workflow_run_id,
            "trace_id": str(snapshot.get("trace_id") or workflow_run_id),
            "dispatch_id": str(worker.get("dispatch_id") or ""),
            "worker_id": str(worker.get("worker_id") or ""),
            "step_run_id": str(worker.get("step_run_id") or ""),
            "admission_id": str(worker.get("admission_id") or ""),
            "lease_expires_at": lease_expires_at,
            "observed_at": observed_at,
        }
        if not all(
            context[key]
            for key in ("dispatch_id", "worker_id", "step_run_id", "admission_id")
        ):
            errors.append(
                {
                    "workflow_run_id": workflow_run_id,
                    "error": "expired worker context is incomplete",
                }
            )
            continue
        if not apply:
            due.append({**context, "action": "would_expire"})
            continue

        try:
            event = expire_worker_lease(
                Path(omo_dir),
                workflow_run_id=workflow_run_id,
                trace_id=context["trace_id"],
                dispatch_id=context["dispatch_id"],
                worker_id=context["worker_id"],
                step_run_id=context["step_run_id"],
                admission_id=context["admission_id"],
                now=observed_at,
                reason=reason,
            )
        except WorkerLifecycleError as exc:
            errors.append({"workflow_run_id": workflow_run_id, "error": str(exc)})
            continue
        expired.append(
            {
                **context,
                "action": "expired",
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
            }
        )

    return {
        "schema": "workflow-mesh-watchdog/v1",
        "mode": "apply" if apply else "dry_run",
        "observed_at": observed_at,
        "run_count": len(run_ids),
        "worker_count": worker_count,
        "due_count": len(due),
        "expired_count": len(expired),
        "due": due,
        "expired": expired,
        "errors": errors,
    }


__all__ = [
    "WorkerLifecycleError",
    "acknowledge_worker",
    "expire_worker_lease",
    "reclaim_worker",
    "record_step_dispatch",
    "renew_worker_lease",
    "scan_worker_leases",
]
