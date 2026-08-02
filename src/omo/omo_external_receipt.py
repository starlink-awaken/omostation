"""受治理的外部调用 receipt 到 Workflow Mesh 证据回写 broker。

执行方负责产生 credential-free receipt；OMO 负责校验上下文、规范化最小证据
payload，并以幂等的 ``EvidenceRecorded`` 事件写入 Workflow Mesh。这个模块不
调用 provider，也不接触外部原文或凭据。
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .workflow_mesh import WorkflowMeshStore, new_workflow_event

RECEIPT_SCHEMA = "external-connection-receipt/v1"
EVIDENCE_KIND = "external_connection"
_REQUIRED_FIELDS = frozenset(
    {
        "receipt_id",
        "trace_id",
        "resource_id",
        "operation",
        "result_state",
        "observed_at",
        "provenance_ref",
        "policy_digest",
    }
)
_EVIDENCE_STATES = frozenset({"succeeded", "degraded"})
_FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "content",
        "input_data",
        "output",
        "output_data",
        "password",
        "private_key",
        "raw_content",
        "raw_input",
        "raw_output",
        "refresh_token",
        "secret",
    }
)


class ExternalReceiptError(ValueError):
    """Receipt 不能安全地成为 Workflow Mesh 证据。"""


def _as_mapping(receipt: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(receipt, Mapping):
        return receipt
    to_dict = getattr(receipt, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return value
    raise ExternalReceiptError("receipt must be a mapping or expose to_dict()")


def _reject_forbidden(value: Any, path: str = "receipt") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalReceiptError(
                    f"forbidden raw or secret field: {path}.{key}"
                )
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExternalReceiptError(f"receipt missing required field: {field_name}")
    return text


def _validate_timestamp(value: Any) -> str:
    text = _required_text(value, "observed_at")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalReceiptError(f"invalid receipt timestamp: {text}") from exc
    return text


def _validate_digest(value: Any) -> str | None:
    if value in (None, ""):
        return None
    digest = str(value).strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ExternalReceiptError("output_digest must be a SHA-256 hex digest")
    return digest


def _normalise_receipt(receipt: Mapping[str, Any] | Any) -> dict[str, Any]:
    value = dict(_as_mapping(receipt))
    _reject_forbidden(value)
    missing = sorted(_REQUIRED_FIELDS - value.keys())
    if missing:
        raise ExternalReceiptError(f"receipt missing required fields: {missing}")
    result_state = _required_text(value["result_state"], "result_state").lower()
    if result_state not in _EVIDENCE_STATES:
        raise ExternalReceiptError(
            "only succeeded/degraded receipts may become EvidenceRecorded; "
            f"received {result_state!r}"
        )
    decision_factors = value.get("decision_factors", {})
    if not isinstance(decision_factors, Mapping):
        raise ExternalReceiptError("decision_factors must be an object")
    output_digest = _validate_digest(value.get("output_digest"))
    if result_state == "succeeded" and output_digest is None:
        raise ExternalReceiptError("succeeded receipt requires output_digest")
    return {
        "receipt_id": _required_text(value["receipt_id"], "receipt_id"),
        "trace_id": _required_text(value["trace_id"], "trace_id"),
        "resource_id": _required_text(value["resource_id"], "resource_id"),
        "operation": _required_text(value["operation"], "operation"),
        "result_state": result_state,
        "observed_at": _validate_timestamp(value["observed_at"]),
        "provenance_ref": _required_text(value["provenance_ref"], "provenance_ref"),
        "policy_digest": _required_text(value["policy_digest"], "policy_digest"),
        "decision_factors": dict(decision_factors),
        "output_digest": output_digest,
        "error_code": str(value.get("error_code") or "").strip() or None,
    }


def _event_id(workflow_run_id: str, receipt_id: str) -> str:
    material = f"{workflow_run_id}\n{receipt_id}".encode()
    return f"external-evidence:{hashlib.sha256(material).hexdigest()}"


def record_external_receipt(
    omo_dir: Path | str,
    receipt: Mapping[str, Any] | Any,
    *,
    workflow_run_id: str,
    step_run_id: str | None = None,
    producer: str = "external-connection-fabric",
) -> dict[str, Any]:
    """将成功/降级 receipt 幂等回写为一个 ``EvidenceRecorded`` 事件。

    只接受已经完成外部调用的最小 receipt。它不会替调用方执行 admission、
    provider 或补偿；这些仍由各自控制面负责。
    """
    run_id = _required_text(workflow_run_id, "workflow_run_id")
    step = str(step_run_id or "").strip() or None
    normalized = _normalise_receipt(receipt)
    evidence_id = f"external:{normalized['resource_id']}:{normalized['receipt_id']}"
    payload: dict[str, Any] = {
        "evidence_id": evidence_id,
        "evidence_schema": RECEIPT_SCHEMA,
        "kind": EVIDENCE_KIND,
        "uri": f"external://{normalized['resource_id']}/{normalized['operation']}",
        "sha256": normalized["output_digest"],
        "resource_id": normalized["resource_id"],
        "trace_id": normalized["trace_id"],
        "workflow_run_id": run_id,
        "result_state": normalized["result_state"],
        "observed_at": normalized["observed_at"],
        "provenance_ref": normalized["provenance_ref"],
        "policy_digest": normalized["policy_digest"],
        "receipt_id": normalized["receipt_id"],
        "decision_factors": normalized["decision_factors"],
    }
    if normalized["error_code"]:
        payload["error_code"] = normalized["error_code"]
    if step:
        payload["step_run_id"] = step
    event = new_workflow_event(
        "EvidenceRecorded",
        run_id,
        trace_id=normalized["trace_id"],
        producer=producer,
        payload=payload,
        idempotency_key=f"external-evidence:{run_id}:{normalized['receipt_id']}",
    )
    # Receipt identity and observed time are stable, so retries create the exact
    # same event and WorkflowMeshStore can return the existing append-only record.
    event["event_id"] = _event_id(run_id, normalized["receipt_id"])
    event["occurred_at"] = normalized["observed_at"]
    return WorkflowMeshStore(omo_dir).append(event)


__all__ = [
    "EVIDENCE_KIND",
    "RECEIPT_SCHEMA",
    "ExternalReceiptError",
    "record_external_receipt",
]
