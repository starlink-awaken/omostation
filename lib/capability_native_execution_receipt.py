"""Frozen v1 facade for pure native execution receipts and replay decisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from capability_native_cleanup import (
    CLEANUP_SCHEMA,
    build_native_cleanup_proof,
    validate_native_cleanup_proof,
)
from capability_native_execution_model import (
    MATERIAL_SCHEMA,
    NativeExecutionReceiptError,
    build_native_execution_material,
    canonical_digest,
    derive_invocation_id,
    enforce_value_firewall,
    require_digest,
    require_safe_id,
    validate_native_execution_material,
)

EXECUTION_SCHEMA = "native-execution-receipt/v1"
MARKER_SCHEMA = "native-execution-marker/v1"
TRANSPORT_STATES = {"confirmed", "failed", "uncertain"}
RECEIPT_FIELDS = {
    "schema",
    "status",
    "invocation_id",
    "material",
    "transport_state",
    "outcome",
    "action_receipt",
    "cleanup_proof",
    "cleanup_digest",
    "fallback",
    "states",
    "value_indicator_policy",
    "receipt_digest",
}
MARKER_FIELDS = {"schema", "status", "invocation_id", "material_digest", "receipt_digest"}


def _mapping(value: Any, fields: set[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value.keys()) != fields:
        raise NativeExecutionReceiptError(code)
    return value


def _validate_outcome(value: Any, transport: str) -> dict[str, Any]:
    outcome = _mapping(value, {"status", "failure_code", "result_digest"}, "native_invocation_failed")
    status, failure, result = outcome.get("status"), outcome.get("failure_code"), outcome.get("result_digest")
    expected = {
        "confirmed": ("succeeded", None),
        "failed": ("failed", "native_invocation_failed"),
        "uncertain": ("unknown", None),
    }[transport]
    if (status, failure) != expected:
        raise NativeExecutionReceiptError("native_invocation_failed")
    if transport == "uncertain":
        if result is not None:
            raise NativeExecutionReceiptError("native_invocation_failed")
    else:
        result = require_digest(result, "native_invocation_failed")
    return {"status": status, "failure_code": failure, "result_digest": result}


def _validate_action(value: Any, *, effect: str, transport: str) -> dict[str, Any]:
    action = _mapping(value, {"status", "id", "digest"}, "execution_evidence_missing")
    status = action.get("status")
    if status == "terminal":
        action_id = require_safe_id(action.get("id"), "execution_evidence_missing")
        digest = require_digest(action.get("digest"), "execution_evidence_missing")
    elif isinstance(status, str) and status in {"missing", "not_applicable"}:
        if action.get("id") is not None or action.get("digest") is not None:
            raise NativeExecutionReceiptError("execution_evidence_missing")
        action_id, digest = None, None
    else:
        raise NativeExecutionReceiptError("execution_evidence_missing")
    expected = "missing" if transport == "uncertain" else (
        "terminal" if effect == "effectful" else "not_applicable"
    )
    if status != expected:
        raise NativeExecutionReceiptError("execution_evidence_missing")
    return {"status": status, "id": action_id, "digest": digest}


def _validate_fixed_state(value: Any) -> dict[str, bool]:
    states = _mapping(
        value, {"invoked", "evidenced", "independently_verified"}, "native_execution_unprovable"
    )
    if type(states.get("invoked")) is not bool or states.get("invoked") is not True:
        raise NativeExecutionReceiptError("native_execution_unprovable")
    if states.get("evidenced") is not False or states.get("independently_verified") is not False:
        raise NativeExecutionReceiptError("value_promotion_forbidden")
    return {"invoked": True, "evidenced": False, "independently_verified": False}


def validate_native_execution_receipt(receipt: Any) -> dict[str, Any]:
    """Replay-validate a completed digest-only receipt without side effects."""
    enforce_value_firewall(receipt)
    item = _mapping(receipt, RECEIPT_FIELDS, "native_execution_unprovable")
    if item.get("schema") != EXECUTION_SCHEMA or item.get("status") != "completed":
        raise NativeExecutionReceiptError("native_execution_unprovable")
    material = validate_native_execution_material(item.get("material"))
    invocation_id = derive_invocation_id(material)
    if item.get("invocation_id") != invocation_id:
        raise NativeExecutionReceiptError("execution_conflict")
    transport = item.get("transport_state")
    if not isinstance(transport, str) or transport not in TRANSPORT_STATES:
        raise NativeExecutionReceiptError("transport_uncertain")
    outcome = _validate_outcome(item.get("outcome"), transport)
    effect = material["effect_classification"]
    action = _validate_action(item.get("action_receipt"), effect=effect, transport=transport)
    cleanup = validate_native_cleanup_proof(item.get("cleanup_proof"))
    if (
        cleanup["invocation_id"] != invocation_id
        or cleanup["capability_kind"] != material["capability"]["kind"]
        or item.get("cleanup_digest") != cleanup["receipt_digest"]
    ):
        raise NativeExecutionReceiptError("cleanup_unproven")
    if transport != "uncertain" and cleanup["status"] != "proved":
        raise NativeExecutionReceiptError("cleanup_unproven")
    fallback = _mapping(item.get("fallback"), {"used"}, "fallback_forbidden")
    if fallback.get("used") is not False:
        raise NativeExecutionReceiptError("fallback_forbidden")
    states = _validate_fixed_state(item.get("states"))
    if item.get("value_indicator_policy") is not False:
        raise NativeExecutionReceiptError("value_promotion_forbidden")
    canonical = {
        "schema": EXECUTION_SCHEMA,
        "status": "completed",
        "invocation_id": invocation_id,
        "material": material,
        "transport_state": transport,
        "outcome": outcome,
        "action_receipt": action,
        "cleanup_proof": cleanup,
        "cleanup_digest": cleanup["receipt_digest"],
        "fallback": {"used": False},
        "states": states,
        "value_indicator_policy": False,
    }
    if item.get("receipt_digest") != canonical_digest(canonical):
        raise NativeExecutionReceiptError("native_execution_unprovable")
    return {**canonical, "receipt_digest": item["receipt_digest"]}


def build_native_execution_receipt(
    *,
    material: Mapping[str, Any],
    transport_state: str,
    outcome: str,
    failure_code: Optional[str],  # noqa: UP045 -- Python 3.9 contract
    result_digest: Optional[str],  # noqa: UP045 -- Python 3.9 contract
    action_receipt: Mapping[str, Any],
    cleanup_proof: Mapping[str, Any],
) -> dict[str, Any]:
    material_v1 = validate_native_execution_material(material)
    cleanup = validate_native_cleanup_proof(cleanup_proof)
    receipt: dict[str, Any] = {
        "schema": EXECUTION_SCHEMA,
        "status": "completed",
        "invocation_id": derive_invocation_id(material_v1),
        "material": material_v1,
        "transport_state": transport_state,
        "outcome": {"status": outcome, "failure_code": failure_code, "result_digest": result_digest},
        "action_receipt": dict(action_receipt),
        "cleanup_proof": cleanup,
        "cleanup_digest": cleanup["receipt_digest"],
        "fallback": {"used": False},
        "states": {"invoked": True, "evidenced": False, "independently_verified": False},
        "value_indicator_policy": False,
    }
    receipt["receipt_digest"] = canonical_digest(receipt)
    return validate_native_execution_receipt(receipt)


def validate_native_execution_marker(marker: Any) -> dict[str, Any]:
    item = _mapping(marker, MARKER_FIELDS, "native_execution_unprovable")
    if item.get("schema") != MARKER_SCHEMA or item.get("status") != "started":
        raise NativeExecutionReceiptError("native_execution_unprovable")
    invocation_id = require_digest(item.get("invocation_id"), "native_execution_unprovable")
    material_digest = require_digest(item.get("material_digest"), "native_execution_unprovable")
    canonical = {
        "schema": MARKER_SCHEMA,
        "status": "started",
        "invocation_id": invocation_id,
        "material_digest": material_digest,
    }
    if item.get("receipt_digest") != canonical_digest(canonical):
        raise NativeExecutionReceiptError("native_execution_unprovable")
    return {**canonical, "receipt_digest": item["receipt_digest"]}


def build_native_execution_marker(material: Any) -> dict[str, Any]:
    material_v1 = validate_native_execution_material(material)
    marker: dict[str, Any] = {
        "schema": MARKER_SCHEMA,
        "status": "started",
        "invocation_id": derive_invocation_id(material_v1),
        "material_digest": canonical_digest(material_v1),
    }
    marker["receipt_digest"] = canonical_digest(marker)
    return validate_native_execution_marker(marker)


def classify_native_execution_replay(existing: Any, material: Any) -> dict[str, Any]:
    invocation_id = derive_invocation_id(material)
    if existing is None:
        return {"classification": "needs_durable_start", "call_allowed": False, "invocation_id": invocation_id}
    if isinstance(existing, Mapping) and existing.get("schema") == MARKER_SCHEMA:
        marker = validate_native_execution_marker(existing)
        expected = build_native_execution_marker(material)
        if marker != expected:
            raise NativeExecutionReceiptError("execution_conflict")
        raise NativeExecutionReceiptError("transport_uncertain")
    completed = validate_native_execution_receipt(existing)
    if completed["invocation_id"] != invocation_id:
        raise NativeExecutionReceiptError("execution_conflict")
    return {
        "classification": "existing",
        "call_allowed": False,
        "invocation_id": invocation_id,
        "receipt": completed,
    }


__all__ = [
    "CLEANUP_SCHEMA", "EXECUTION_SCHEMA", "MARKER_SCHEMA", "MATERIAL_SCHEMA",
    "NativeExecutionReceiptError", "build_native_cleanup_proof", "build_native_execution_marker",
    "build_native_execution_material", "build_native_execution_receipt", "canonical_digest",
    "classify_native_execution_replay", "derive_invocation_id", "validate_native_cleanup_proof",
    "validate_native_execution_marker", "validate_native_execution_material",
    "validate_native_execution_receipt",
]
