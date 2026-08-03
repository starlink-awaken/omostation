"""受治理的无副作用 sandbox ToolPack 执行器。

This module deliberately does not call a provider, read source content, or run
an arbitrary command. It proves the Mesh execution edge with one deterministic
tool: ``sandbox.digest_ref`` hashes a safe reference and its existing digest.
The result is recorded through the normal Mesh event and receipt brokers.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_external_receipt import record_external_receipt
from .workflow_mesh import (
    TOOL_OUTCOMES,
    WorkflowMeshEventError,
    WorkflowMeshStore,
    new_workflow_event,
)

SANDBOX_TOOL_SCHEMA = "sandbox-tool-invocation/v1"
SANDBOX_TOOL_RECEIPT_SCHEMA = "sandbox-tool-receipt/v1"
SANDBOX_TOOL_ID = "sandbox.digest_ref"
SANDBOX_CAPABILITY = "sandbox.tool.invoke"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_REF = re.compile(r"^(?:artifact|bos|sandbox)://[^\s]{1,480}$")


class SandboxToolError(ValueError):
    """Sandbox tool invocation failed its safety or Mesh contract."""


def _utc(value: str | None = None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _stamp(value: str | None = None) -> str:
    return _utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _existing(store: WorkflowMeshStore, idempotency_key: str) -> dict[str, Any] | None:
    return next(
        (
            event
            for event in store.events()
            if event.get("idempotency_key") == idempotency_key
        ),
        None,
    )


def _append(
    store: WorkflowMeshStore,
    event_type: str,
    workflow_run_id: str,
    *,
    trace_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    prior = _existing(store, idempotency_key)
    if prior is not None:
        if prior.get("event_type") != event_type or prior.get("payload") != payload:
            raise SandboxToolError(f"conflicting sandbox event: {idempotency_key}")
        return prior
    try:
        return store.append(
            new_workflow_event(
                event_type,
                workflow_run_id,
                trace_id=trace_id,
                producer="omo.sandbox_tool_runner",
                idempotency_key=idempotency_key,
                payload=payload,
            )
        )
    except WorkflowMeshEventError as exc:
        raise SandboxToolError(str(exc)) from exc


def _validate_request(tool_id: str, input_ref: str, input_digest: str) -> None:
    if tool_id != SANDBOX_TOOL_ID:
        raise SandboxToolError(f"unsupported sandbox tool: {tool_id}")
    if not _SAFE_REF.fullmatch(input_ref):
        raise SandboxToolError(
            "input_ref must be an artifact://, bos://, or sandbox:// reference"
        )
    if not _SHA256.fullmatch(input_digest.lower()):
        raise SandboxToolError("input_digest must be a SHA-256 hex digest")


def _validate_live_context(
    store: WorkflowMeshStore,
    *,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    observed_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = store.snapshot(workflow_run_id)
    if snapshot.get("state") in {"unknown", "planned", "closed", "cancelled"}:
        raise SandboxToolError(
            f"workflow is not executable in sandbox: {snapshot.get('state')}"
        )
    if snapshot.get("trace_id") != trace_id:
        raise SandboxToolError("sandbox trace_id mismatch")
    admission = snapshot.get("admission")
    if not isinstance(admission, dict) or admission.get("admission_id") != admission_id:
        raise SandboxToolError("sandbox admission_id mismatch")
    try:
        if observed_at >= _utc(str(admission["expires_at"])):
            raise SandboxToolError("sandbox admission grant has expired")
    except KeyError as exc:
        raise SandboxToolError("sandbox admission grant has no expiry") from exc
    capabilities = {str(item) for item in admission.get("capabilities", [])}
    if SANDBOX_CAPABILITY not in capabilities:
        raise SandboxToolError(f"admission lacks capability: {SANDBOX_CAPABILITY}")
    step = snapshot.get("step_runs", {}).get(step_run_id)
    if not isinstance(step, dict) or step.get("admission_id") != admission_id:
        raise SandboxToolError(f"unknown admitted StepRun: {step_run_id}")
    worker = snapshot.get("worker")
    if not isinstance(worker, dict) or worker.get("state") not in {
        "acknowledged",
        "active",
    }:
        raise SandboxToolError("worker must ACK before sandbox invocation")
    try:
        if observed_at >= _utc(str(worker["lease_expires_at"])):
            raise SandboxToolError("worker lease has expired")
    except KeyError as exc:
        raise SandboxToolError("worker lease has no expiry") from exc
    for field, expected in (
        ("dispatch_id", dispatch_id),
        ("worker_id", worker_id),
        ("step_run_id", step_run_id),
        ("admission_id", admission_id),
    ):
        if worker.get(field) != expected:
            raise SandboxToolError(f"sandbox worker context mismatch: {field}")
    return snapshot, admission


def run_sandbox_tool(
    omo_dir: Path | str,
    *,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    tool_id: str = SANDBOX_TOOL_ID,
    input_ref: str,
    input_digest: str,
    outcome: str = "succeeded",
    now: str | None = None,
) -> dict[str, Any]:
    """Run one deterministic sandbox ToolPack operation and persist its receipt.

    The admission and live worker lease are checked immediately before any
    event is appended. Retries reuse the same invocation identity and never
    create a second receipt.
    """
    input_ref = str(input_ref or "").strip()
    input_digest = str(input_digest or "").strip().lower()
    outcome = str(outcome or "").strip().lower()
    if outcome not in TOOL_OUTCOMES:
        raise SandboxToolError("outcome must be succeeded, failed, or unavailable")
    _validate_request(tool_id, input_ref, input_digest)
    observed_at = _utc(now)
    store = WorkflowMeshStore(omo_dir)
    snapshot, admission = _validate_live_context(
        store,
        workflow_run_id=workflow_run_id,
        trace_id=trace_id,
        dispatch_id=dispatch_id,
        worker_id=worker_id,
        step_run_id=step_run_id,
        admission_id=admission_id,
        observed_at=observed_at,
    )
    invocation_material = {
        "workflow_run_id": workflow_run_id,
        "step_run_id": step_run_id,
        "dispatch_id": dispatch_id,
        "tool_id": tool_id,
        "input_ref": input_ref,
        "input_digest": input_digest,
    }
    invocation_id = f"sandbox-invocation:{_digest(invocation_material)}"
    invocation_key = f"{workflow_run_id}:sandbox-tool:{step_run_id}"
    invocation_payload = {
        "invocation_id": invocation_id,
        "tool_id": tool_id,
        "operation": "digest_ref",
        "input_ref": input_ref,
        "input_digest": input_digest,
        "activation": "sandbox",
        "external_side_effects": "disabled",
        "dispatch_id": dispatch_id,
        "worker_id": worker_id,
        "step_run_id": step_run_id,
        "admission_id": admission_id,
        "request_digest": _digest(invocation_material),
        "outcome": outcome,
    }
    prior = _existing(store, invocation_key)
    if prior is not None and prior.get("payload") != invocation_payload:
        raise SandboxToolError("sandbox invocation replay changed its request")
    event_types = {
        str(event.get("event_type"))
        for event in store.events()
        if event.get("workflow_run_id") == workflow_run_id
    }
    if "WorkflowSucceeded" in event_types and prior is None:
        raise SandboxToolError(
            "workflow already succeeded without this sandbox invocation"
        )

    step_started = _append(
        store,
        "StepStarted",
        workflow_run_id,
        trace_id=trace_id,
        idempotency_key=f"{workflow_run_id}:sandbox-step-started:{step_run_id}",
        payload={
            "step_run_id": step_run_id,
            "step_name": "sandbox.digest_ref",
            "attempt": 1,
            "admission_id": admission_id,
        },
    )
    invocation = _append(
        store,
        "ToolInvocationRecorded",
        workflow_run_id,
        trace_id=trace_id,
        idempotency_key=invocation_key,
        payload=invocation_payload,
    )
    result_event_type = {
        "failed": "StepFailed",
        "unavailable": "BackendUnavailable",
    }.get(outcome)
    result_event = None
    if result_event_type is None:
        result_event = _append(
            store,
            "WorkflowSucceeded",
            workflow_run_id,
            trace_id=trace_id,
            idempotency_key=f"{workflow_run_id}:sandbox-workflow-succeeded",
            payload={"step_count": 1, "execution_mode": "sandbox"},
        )
    else:
        error_code = (
            "SANDBOX_TOOL_FAILED"
            if outcome == "failed"
            else "SANDBOX_BACKEND_UNAVAILABLE"
        )
        result_event = _append(
            store,
            result_event_type,
            workflow_run_id,
            trace_id=trace_id,
            idempotency_key=f"{workflow_run_id}:sandbox-tool-result:{step_run_id}",
            payload={
                "step_run_id": step_run_id,
                "admission_id": admission_id,
                "dispatch_id": dispatch_id,
                "worker_id": worker_id,
                "error_code": error_code,
                "outcome": outcome,
            },
        )
    observed_at_stamp = _stamp(now)
    output_digest = _digest(
        {
            "tool_id": tool_id,
            "input_ref": input_ref,
            "input_digest": input_digest,
            "request_digest": invocation_payload["request_digest"],
        }
    )
    if outcome != "succeeded":
        events = [
            step_started["event_id"],
            invocation["event_id"],
            result_event["event_id"],
        ]
        return {
            "schema": SANDBOX_TOOL_SCHEMA,
            "status": "replayed" if prior is not None else "executed",
            "activation": "sandbox",
            "external_side_effects": "disabled",
            "workflow_run_id": workflow_run_id,
            "step_run_id": step_run_id,
            "invocation_id": invocation_id,
            "tool_id": tool_id,
            "outcome": outcome,
            "error_code": result_event["payload"]["error_code"],
            "output_digest": None,
            "events": events,
            "receipt_event_id": None,
            "receipt_schema": SANDBOX_TOOL_RECEIPT_SCHEMA,
            "run_state": WorkflowMeshStore(omo_dir).snapshot(workflow_run_id)["state"],
            "worker_state": snapshot.get("worker", {}).get("state"),
        }
    receipt = {
        "receipt_id": invocation_id,
        "trace_id": trace_id,
        "resource_id": f"sandbox-toolpack:{tool_id}",
        "operation": "digest_ref",
        "result_state": outcome,
        "observed_at": observed_at_stamp,
        "provenance_ref": f"sandbox://invocations/{invocation_id}",
        "policy_digest": str(admission["policy_digest"]),
        "decision_factors": {
            "tool_id": tool_id,
            "activation": "sandbox",
            "external_side_effects": "disabled",
            "input_ref": input_ref,
            "input_digest": input_digest,
            "request_digest": invocation_payload["request_digest"],
        },
        "output_digest": output_digest,
    }
    evidence = record_external_receipt(
        omo_dir,
        receipt,
        workflow_run_id=workflow_run_id,
        step_run_id=step_run_id,
        producer="omo.sandbox_tool_runner",
    )
    return {
        "schema": SANDBOX_TOOL_SCHEMA,
        "status": "replayed" if prior is not None else "executed",
        "activation": "sandbox",
        "external_side_effects": "disabled",
        "workflow_run_id": workflow_run_id,
        "step_run_id": step_run_id,
        "invocation_id": invocation_id,
        "tool_id": tool_id,
        "output_digest": output_digest,
        "outcome": outcome,
        "events": [
            step_started["event_id"],
            invocation["event_id"],
            result_event["event_id"],
            evidence["event_id"],
        ],
        "receipt_event_id": evidence["event_id"],
        "receipt_schema": SANDBOX_TOOL_RECEIPT_SCHEMA,
        "run_state": WorkflowMeshStore(omo_dir).snapshot(workflow_run_id)["state"],
        "worker_state": snapshot.get("worker", {}).get("state"),
    }


__all__ = [
    "SANDBOX_CAPABILITY",
    "SANDBOX_TOOL_ID",
    "SANDBOX_TOOL_RECEIPT_SCHEMA",
    "SANDBOX_TOOL_SCHEMA",
    "SandboxToolError",
    "run_sandbox_tool",
]
