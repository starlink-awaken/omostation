"""Durable approval timeout lifecycle for Workflow Mesh.

Mirrors worker_lifecycle.py: approval requests carry a configurable timeout,
a periodic scanner finds expired approvals, and expiry is recorded as an
ApprovalTimeout event in the append-only event log.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .workflow_mesh import WorkflowMeshEventError, WorkflowMeshStore, new_workflow_event


class ApprovalLifecycleError(ValueError):
    """An approval lifecycle transition failed its mesh contract."""


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
            raise ApprovalLifecycleError(
                f"conflicting approval lifecycle event: {idempotency_key}"
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
        raise ApprovalLifecycleError(str(exc)) from exc


def request_approval(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    approval_id: str = "workflow",
    timeout_seconds: int = 604_800,
    now: str | None = None,
) -> dict[str, Any]:
    """Record an approval request with a configurable timeout.

    Default timeout is 7 days (604800 seconds). The timeout is stored as
    ``timeout_at`` in the event payload so the scanner can find expired
    approvals without re-computing from ``requested_at + timeout_seconds``.
    """
    if timeout_seconds <= 0:
        raise ApprovalLifecycleError("timeout_seconds must be positive")
    store = _store(omo_dir)
    snapshot = store.snapshot(workflow_run_id)
    if snapshot.get("state") not in {"running"}:
        raise ApprovalLifecycleError(
            f"cannot request approval in state: {snapshot.get('state')}"
        )
    requested_at = _stamp(now)
    timeout_at = _stamp(
        (_utc(requested_at) + timedelta(seconds=timeout_seconds)).isoformat()
    )
    event_key = f"{workflow_run_id}:approval-requested:{approval_id}"
    prior = _existing(store, event_key)
    if prior is not None:
        return prior
    payload = {
        "approval_id": approval_id,
        "requested_at": requested_at,
        "timeout_at": timeout_at,
        "timeout_seconds": timeout_seconds,
    }
    return _append(
        store,
        "ApprovalRequested",
        workflow_run_id,
        trace_id=trace_id,
        producer="omo.approval_lifecycle",
        idempotency_key=event_key,
        payload=payload,
    )


def grant_approval(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    approval_id: str = "workflow",
    now: str | None = None,
) -> dict[str, Any]:
    """Record an approval grant, transitioning back to running."""
    store = _store(omo_dir)
    snapshot = store.snapshot(workflow_run_id)
    if snapshot.get("state") != "waiting_approval":
        raise ApprovalLifecycleError(
            f"cannot grant approval in state: {snapshot.get('state')}"
        )
    approval = snapshot.get("approvals", {}).get(approval_id)
    if not approval or approval.get("state") != "requested":
        raise ApprovalLifecycleError(
            f"approval '{approval_id}' is not in requested state"
        )
    event_key = f"{workflow_run_id}:approval-granted:{approval_id}"
    prior = _existing(store, event_key)
    if prior is not None:
        return prior
    payload = {
        "approval_id": approval_id,
        "granted_at": _stamp(now),
    }
    return _append(
        store,
        "ApprovalGranted",
        workflow_run_id,
        trace_id=trace_id,
        producer="omo.approval_lifecycle",
        idempotency_key=event_key,
        payload=payload,
    )


def expire_approval_timeout(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    approval_id: str = "workflow",
    now: str | None = None,
    reason: str = "approval_timeout",
) -> dict[str, Any]:
    """Mark an approval as timed out after its timeout_at has passed."""
    store = _store(omo_dir)
    snapshot = store.snapshot(workflow_run_id)
    if snapshot.get("state") != "waiting_approval":
        raise ApprovalLifecycleError(
            f"cannot expire approval timeout in state: {snapshot.get('state')}"
        )
    approval = snapshot.get("approvals", {}).get(approval_id)
    if not approval or approval.get("state") != "requested":
        raise ApprovalLifecycleError(
            f"approval '{approval_id}' is not in requested state"
        )
    timeout_at = str(approval.get("timeout_at") or "")
    if not timeout_at:
        raise ApprovalLifecycleError(f"approval '{approval_id}' has no timeout_at")
    observed_at = _stamp(now)
    if _utc(observed_at) < _utc(timeout_at):
        raise ApprovalLifecycleError("approval timeout has not expired")
    event_key = f"{workflow_run_id}:approval-timeout:{approval_id}"
    prior = _existing(store, event_key)
    if prior is not None:
        return prior
    payload = {
        "approval_id": approval_id,
        "timeout_at": timeout_at,
        "expired_at": observed_at,
        "reason": reason,
    }
    return _append(
        store,
        "ApprovalTimeout",
        workflow_run_id,
        trace_id=trace_id,
        producer="omo.approval_lifecycle",
        idempotency_key=event_key,
        payload=payload,
    )


def scan_approval_timeouts(
    omo_dir: Path | str,
    *,
    now: str | None = None,
    apply: bool = False,
    reason: str = "approval_timeout",
) -> dict[str, Any]:
    """Find expired approval timeouts and optionally persist timeout events.

    Default is read-only (dry_run). ``apply=True`` appends ``ApprovalTimeout``
    events for each expired approval.
    """
    if not str(reason).strip():
        raise ApprovalLifecycleError("watchdog expiry reason is required")

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

    for workflow_run_id in run_ids:
        try:
            snapshot = store.snapshot(workflow_run_id)
        except (WorkflowMeshEventError, OSError, ValueError) as exc:
            errors.append({"workflow_run_id": workflow_run_id, "error": str(exc)})
            continue

        if snapshot.get("state") != "waiting_approval":
            continue

        approvals = snapshot.get("approvals", {})
        for approval_id, approval in approvals.items():
            if not isinstance(approval, dict):
                continue
            if approval.get("state") != "requested":
                continue

            timeout_at = str(approval.get("timeout_at") or "")
            if not timeout_at:
                errors.append(
                    {
                        "workflow_run_id": workflow_run_id,
                        "approval_id": approval_id,
                        "error": "pending approval has no timeout_at",
                    }
                )
                continue

            try:
                is_expired = _utc(observed_at) >= _utc(timeout_at)
            except ValueError as exc:
                errors.append(
                    {
                        "workflow_run_id": workflow_run_id,
                        "approval_id": approval_id,
                        "error": str(exc),
                    }
                )
                continue

            if not is_expired:
                continue

            context = {
                "workflow_run_id": workflow_run_id,
                "trace_id": str(snapshot.get("trace_id") or workflow_run_id),
                "approval_id": approval_id,
                "requested_at": approval.get("requested_at"),
                "timeout_at": timeout_at,
                "observed_at": observed_at,
            }

            if not apply:
                due.append({**context, "action": "would_expire"})
                continue

            try:
                event = expire_approval_timeout(
                    Path(omo_dir),
                    workflow_run_id=workflow_run_id,
                    trace_id=context["trace_id"],
                    approval_id=approval_id,
                    now=observed_at,
                    reason=reason,
                )
            except ApprovalLifecycleError as exc:
                errors.append(
                    {
                        "workflow_run_id": workflow_run_id,
                        "approval_id": approval_id,
                        "error": str(exc),
                    }
                )
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
        "schema": "approval-timeout-watchdog/v1",
        "mode": "apply" if apply else "dry_run",
        "observed_at": observed_at,
        "run_count": len(run_ids),
        "waiting_count": sum(
            1
            for rid in run_ids
            if _safe_snapshot(store, rid, errors).get("state") == "waiting_approval"
        ),
        "due_count": len(due),
        "expired_count": len(expired),
        "due": due,
        "expired": expired,
        "errors": errors,
    }


def _safe_snapshot(
    store: WorkflowMeshStore,
    workflow_run_id: str,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    try:
        return store.snapshot(workflow_run_id)
    except (WorkflowMeshEventError, OSError, ValueError) as exc:
        errors.append({"workflow_run_id": workflow_run_id, "error": str(exc)})
        return {}


__all__ = [
    "ApprovalLifecycleError",
    "expire_approval_timeout",
    "grant_approval",
    "request_approval",
    "scan_approval_timeouts",
]
