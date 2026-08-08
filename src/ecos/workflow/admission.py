"""Workflow Mesh execution admission grants.

ECOS is the policy boundary that creates a short-lived grant. Runtime and
Swarm validate the same portable shape without importing ECOS or OMO.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4


class WorkflowAdmissionError(ValueError):
    """Raised when an execution grant is missing or inconsistent."""


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def admission_proof(grant: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in grant.items() if key != "proof"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def new_admission_grant(
    workflow_run_id: str,
    trace_id: str,
    step_run_ids: list[str],
    *,
    backend: str,
    policy_snapshot: dict[str, Any] | None = None,
    capabilities: list[str] | None = None,
    ttl_seconds: int = 900,
) -> dict[str, Any]:
    issued_at = datetime.now(UTC)
    policy = dict(policy_snapshot or {})
    policy_digest = hashlib.sha256(_canonical(policy)).hexdigest()
    grant: dict[str, Any] = {
        "admission_id": f"adm-{uuid4().hex}",
        "status": "admitted",
        "workflow_run_id": workflow_run_id,
        "trace_id": trace_id,
        "backend": backend,
        "step_run_ids": sorted(set(step_run_ids)),
        "capabilities": sorted(set(capabilities or ["execute"])),
        "policy_digest": policy_digest,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(seconds=ttl_seconds)).isoformat(),
    }
    grant["proof"] = admission_proof(grant)
    return grant


def validate_admission_grant(
    grant: dict[str, Any] | None,
    *,
    workflow_run_id: str,
    step_run_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(grant, dict):
        raise WorkflowAdmissionError("Workflow Mesh execution admission is required")
    required = {
        "admission_id",
        "status",
        "workflow_run_id",
        "trace_id",
        "step_run_ids",
        "capabilities",
        "policy_digest",
        "issued_at",
        "expires_at",
        "proof",
    }
    missing = sorted(required - grant.keys())
    if missing:
        raise WorkflowAdmissionError(f"Admission grant missing fields: {missing}")
    if grant["status"] != "admitted":
        raise WorkflowAdmissionError("Admission grant is not admitted")
    if grant["workflow_run_id"] != workflow_run_id:
        raise WorkflowAdmissionError("Admission grant workflow_run_id mismatch")
    if step_run_id is not None and step_run_id not in grant["step_run_ids"]:
        raise WorkflowAdmissionError(f"StepRun is not admitted: {step_run_id}")
    if grant["proof"] != admission_proof(grant):
        raise WorkflowAdmissionError("Admission grant proof mismatch")
    try:
        expires_at = datetime.fromisoformat(str(grant["expires_at"]))
    except ValueError as exc:
        raise WorkflowAdmissionError("Admission grant expires_at is invalid") from exc
    current = now or datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= current.astimezone(UTC):
        raise WorkflowAdmissionError("Admission grant has expired")
    return grant


def derive_admission_grant(
    parent: dict[str, Any],
    *,
    step_run_ids: list[str],
    backend: str,
) -> dict[str, Any]:
    """Create a child grant for a backend's concrete execution steps."""
    child = dict(parent)
    child["admission_id"] = f"{parent['admission_id']}:{backend}"
    child["backend"] = backend
    child["step_run_ids"] = sorted(set(step_run_ids))
    child["parent_admission_id"] = parent["admission_id"]
    child["proof"] = admission_proof(child)
    return child


__all__ = [
    "WorkflowAdmissionError",
    "admission_proof",
    "derive_admission_grant",
    "new_admission_grant",
    "validate_admission_grant",
]
