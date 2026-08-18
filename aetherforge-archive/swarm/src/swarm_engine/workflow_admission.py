"""Portable validation for Workflow Mesh execution admission grants."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


class WorkflowAdmissionError(ValueError):
    """Raised when a Mesh-tracked node is not authorized to execute."""


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def admission_proof(grant: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in grant.items() if key != "proof"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


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
    if step_run_id is not None and not any(
        step_run_id == admitted or step_run_id.startswith(f"{admitted}:") for admitted in grant["step_run_ids"]
    ):
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


__all__ = ["WorkflowAdmissionError", "admission_proof", "validate_admission_grant"]
