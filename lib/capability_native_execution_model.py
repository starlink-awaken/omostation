"""Frozen v1 material model and privacy primitives for native execution."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from capability_native_receipt import NativeInspectionError, parse_native_selector
from capability_trace_binding import validate_trace_binding

MATERIAL_SCHEMA = "native-execution-material/v1"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:@/-]{1,256}$")
EXECUTABLE_KINDS = {"workflow", "mcp_tool", "bos_service"}
AUTHORIZATION_BY_KIND = {
    "workflow": "workflow-controller",
    "mcp_tool": "mcp-pep",
    "bos_service": "bos-pep",
}
EFFECT_CLASSIFICATIONS = {"read_only", "effectful"}
MATERIAL_FIELDS = {
    "schema",
    "binding",
    "capability",
    "inspection",
    "operation_id",
    "request_digest",
    "admission",
    "authorization_source",
    "effect_classification",
    "execution_attempt",
}


class NativeExecutionReceiptError(ValueError):
    """A native execution contract is unsafe, ambiguous, or not replayable."""


def canonical_digest(value: Any) -> str:
    """Return a strict canonical JSON digest or a stable contract error."""
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise NativeExecutionReceiptError("native_execution_unprovable") from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def require_digest(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise NativeExecutionReceiptError(code)
    return value


def require_safe_id(value: Any, code: str) -> str:
    if (
        not isinstance(value, str)
        or not SAFE_ID_RE.fullmatch(value)
        or ".." in value
        or value.startswith(("/", "~", "\\"))
        or any(ord(char) < 32 for char in value)
    ):
        raise NativeExecutionReceiptError(code)
    return value


def _normalized_key(key: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower().replace("-", "_")
    return re.sub(r"_+", "_", snake)


def enforce_value_firewall(value: Any) -> None:
    """Reject human/value promotion fields, including camel-case aliases."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise NativeExecutionReceiptError("native_execution_unprovable")
            normalized = _normalized_key(key)
            compact = normalized.replace("_", "")
            promotion = (
                compact in {"humanverdict", "decisionoutcome"}
                or "personal" in compact
                or ("value" in compact and ("metric" in compact or "indicator" in compact))
            )
            if promotion and not (normalized == "value_indicator_policy" and child is False):
                raise NativeExecutionReceiptError("value_promotion_forbidden")
            enforce_value_firewall(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            enforce_value_firewall(child)


def _exact_mapping(value: Any, fields: set[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value.keys()) != fields:
        raise NativeExecutionReceiptError(code)
    return value


def _validate_capability(value: Any) -> dict[str, str]:
    capability = _exact_mapping(value, {"kind", "id"}, "native_route_unprovable")
    capability_id = capability.get("id")
    kind = capability.get("kind")
    if not isinstance(capability_id, str) or not isinstance(kind, str):
        raise NativeExecutionReceiptError("native_route_unprovable")
    try:
        _prefix, parsed_kind, _native_id = parse_native_selector(capability_id)
    except (NativeInspectionError, TypeError, ValueError) as exc:
        raise NativeExecutionReceiptError("native_route_unprovable") from exc
    if parsed_kind != kind:
        raise NativeExecutionReceiptError("native_route_unprovable")
    if kind not in EXECUTABLE_KINDS:
        raise NativeExecutionReceiptError("native_execution_unprovable")
    return {"kind": kind, "id": capability_id}


def _validate_inspection(value: Any) -> dict[str, str]:
    item = _exact_mapping(value, {"receipt_digest", "source_digest"}, "inspection_receipt_invalid")
    return {
        "receipt_digest": require_digest(item.get("receipt_digest"), "inspection_receipt_invalid"),
        "source_digest": require_digest(item.get("source_digest"), "inspection_receipt_invalid"),
    }


def _validate_admission(value: Any) -> dict[str, Any]:
    item = _exact_mapping(
        value, {"receipt_digest", "admission_id", "step_run_id", "worker"}, "admission_receipt_invalid"
    )
    worker = _exact_mapping(item.get("worker"), {"status", "id"}, "admission_receipt_invalid")
    status, worker_id = worker.get("status"), worker.get("id")
    if status == "bound":
        worker_id = require_safe_id(worker_id, "admission_receipt_invalid")
    elif status == "not_applicable":
        if worker_id is not None:
            raise NativeExecutionReceiptError("admission_receipt_invalid")
    else:
        raise NativeExecutionReceiptError("admission_receipt_invalid")
    return {
        "receipt_digest": require_digest(item.get("receipt_digest"), "admission_receipt_invalid"),
        "admission_id": require_safe_id(item.get("admission_id"), "admission_receipt_invalid"),
        "step_run_id": require_safe_id(item.get("step_run_id"), "admission_receipt_invalid"),
        "worker": {"status": status, "id": worker_id},
    }


def validate_native_execution_material(material: Any) -> dict[str, Any]:
    """Validate complete execution material against B4-B and B4-C contracts."""
    enforce_value_firewall(material)
    item = _exact_mapping(material, MATERIAL_FIELDS, "native_route_unprovable")
    if item.get("schema") != MATERIAL_SCHEMA:
        raise NativeExecutionReceiptError("native_route_unprovable")
    try:
        binding = validate_trace_binding(item.get("binding", {}))
    except (TypeError, ValueError) as exc:
        raise NativeExecutionReceiptError("native_route_unprovable") from exc
    capability = _validate_capability(item.get("capability"))
    inspection = _validate_inspection(item.get("inspection"))
    operation_id = require_safe_id(item.get("operation_id"), "native_route_unprovable")
    request_digest = require_digest(item.get("request_digest"), "native_route_unprovable")
    admission = _validate_admission(item.get("admission"))
    authorization = item.get("authorization_source")
    if not isinstance(authorization, str) or authorization != AUTHORIZATION_BY_KIND[capability["kind"]]:
        raise NativeExecutionReceiptError("authorization_required")
    effect = item.get("effect_classification")
    if not isinstance(effect, str) or effect not in EFFECT_CLASSIFICATIONS:
        raise NativeExecutionReceiptError("native_route_unprovable")
    attempt = item.get("execution_attempt")
    if type(attempt) is not int or not 1 <= attempt <= 1_000_000:
        raise NativeExecutionReceiptError("native_route_unprovable")
    return {
        "schema": MATERIAL_SCHEMA,
        "binding": binding,
        "capability": capability,
        "inspection": inspection,
        "operation_id": operation_id,
        "request_digest": request_digest,
        "admission": admission,
        "authorization_source": authorization,
        "effect_classification": effect,
        "execution_attempt": attempt,
    }


def build_native_execution_material(**values: Any) -> dict[str, Any]:
    return validate_native_execution_material({"schema": MATERIAL_SCHEMA, **values})


def derive_invocation_id(material: Any) -> str:
    return canonical_digest(validate_native_execution_material(material))
