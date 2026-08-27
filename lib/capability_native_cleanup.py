"""Frozen v1 cleanup proof builder and validator for native execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from capability_native_execution_model import (
    NativeExecutionReceiptError,
    canonical_digest,
    enforce_value_firewall,
    require_digest,
)

CLEANUP_SCHEMA = "native-cleanup-proof/v1"
OWNERSHIP_BY_KIND = {
    "workflow": "workflow_child_run",
    "mcp_tool": "mcp_proxy_entry",
    "bos_service": "bos_action_lease",
}
MEASUREMENT_FIELDS = {
    "owned_lock_count",
    "reference_count_delta",
    "connection_created",
    "connection_disconnected",
    "owned_residue_count",
}
CLEANUP_FIELDS = {
    "schema",
    "capability_kind",
    "invocation_id",
    "ownership_scope",
    "baseline_digest",
    "terminal_digest",
    "measurements",
    "status",
    "failure_code",
    "value_indicator_policy",
    "receipt_digest",
}
COUNT_LIMIT = 1_000_000


def _int_measurement(value: Any, *, signed: bool = False) -> int:
    if type(value) is not int:
        raise NativeExecutionReceiptError("cleanup_unproven")
    minimum = -COUNT_LIMIT if signed else 0
    if not minimum <= value <= COUNT_LIMIT:
        raise NativeExecutionReceiptError("cleanup_unproven")
    return value


def _validate_measurements(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value.keys()) != MEASUREMENT_FIELDS:
        raise NativeExecutionReceiptError("cleanup_unproven")
    created = value.get("connection_created")
    disconnected = value.get("connection_disconnected")
    if type(created) is not bool or type(disconnected) is not bool:
        raise NativeExecutionReceiptError("cleanup_unproven")
    return {
        "owned_lock_count": _int_measurement(value.get("owned_lock_count")),
        "reference_count_delta": _int_measurement(value.get("reference_count_delta"), signed=True),
        "connection_created": created,
        "connection_disconnected": disconnected,
        "owned_residue_count": _int_measurement(value.get("owned_residue_count")),
    }


def _proved(measurements: Mapping[str, Any], baseline: str, terminal: str) -> bool:
    return (
        baseline == terminal
        and measurements["owned_lock_count"] == 0
        and measurements["reference_count_delta"] == 0
        and measurements["owned_residue_count"] == 0
        and measurements["connection_disconnected"] is measurements["connection_created"]
    )


def validate_native_cleanup_proof(proof: Any) -> dict[str, Any]:
    """Validate cleanup measurements without reading runtime state."""
    enforce_value_firewall(proof)
    if not isinstance(proof, Mapping) or set(proof.keys()) != CLEANUP_FIELDS:
        raise NativeExecutionReceiptError("cleanup_unproven")
    if proof.get("schema") != CLEANUP_SCHEMA:
        raise NativeExecutionReceiptError("cleanup_unproven")
    kind = proof.get("capability_kind")
    if (
        not isinstance(kind, str)
        or kind not in OWNERSHIP_BY_KIND
        or proof.get("ownership_scope") != OWNERSHIP_BY_KIND[kind]
    ):
        raise NativeExecutionReceiptError("cleanup_unproven")
    invocation_id = require_digest(proof.get("invocation_id"), "cleanup_unproven")
    baseline = require_digest(proof.get("baseline_digest"), "cleanup_unproven")
    terminal = require_digest(proof.get("terminal_digest"), "cleanup_unproven")
    measurements = _validate_measurements(proof.get("measurements"))
    status, failure = proof.get("status"), proof.get("failure_code")
    if status == "proved":
        if failure is not None or not _proved(measurements, baseline, terminal):
            raise NativeExecutionReceiptError("cleanup_unproven")
    elif status == "unproven":
        if failure != "cleanup_unproven":
            raise NativeExecutionReceiptError("cleanup_unproven")
    else:
        raise NativeExecutionReceiptError("cleanup_unproven")
    if proof.get("value_indicator_policy") is not False:
        raise NativeExecutionReceiptError("value_promotion_forbidden")
    canonical = {
        "schema": CLEANUP_SCHEMA,
        "capability_kind": kind,
        "invocation_id": invocation_id,
        "ownership_scope": proof["ownership_scope"],
        "baseline_digest": baseline,
        "terminal_digest": terminal,
        "measurements": measurements,
        "status": status,
        "failure_code": failure,
        "value_indicator_policy": False,
    }
    if proof.get("receipt_digest") != canonical_digest(canonical):
        raise NativeExecutionReceiptError("cleanup_unproven")
    return {**canonical, "receipt_digest": proof["receipt_digest"]}


def build_native_cleanup_proof(
    *,
    capability_kind: str,
    invocation_id: str,
    ownership_scope: str,
    baseline_digest: str,
    terminal_digest: str,
    measurements: Mapping[str, Any],
    status: str,
    failure_code: Optional[str],  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    proof: dict[str, Any] = {
        "schema": CLEANUP_SCHEMA,
        "capability_kind": capability_kind,
        "invocation_id": invocation_id,
        "ownership_scope": ownership_scope,
        "baseline_digest": baseline_digest,
        "terminal_digest": terminal_digest,
        "measurements": dict(measurements) if isinstance(measurements, Mapping) else measurements,
        "status": status,
        "failure_code": failure_code,
        "value_indicator_policy": False,
    }
    proof["receipt_digest"] = canonical_digest(proof)
    return validate_native_cleanup_proof(proof)
