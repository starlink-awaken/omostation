"""Durable, privacy-safe feedback about a Workflow Mesh outcome."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import AppendOnlyLog, fcntl_lock
from .workflow_mesh import WorkflowMeshStore

OUTCOME_FEEDBACK_SCHEMA = "outcome-feedback/v1"
OUTCOME_FEEDBACK_LOG = Path("_knowledge/workflow-mesh/outcome-feedback.jsonl")
OUTCOME_FEEDBACK_STATES = frozenset(
    {"reviewed", "adopted", "submitted", "dispatched", "cited", "rejected"}
)
ELIGIBLE_WORKFLOW_STATES = frozenset({"succeeded", "verified", "merged", "closed"})
SCENE_BINDING_FIELDS = ("scene_id", "journey_id", "outcome_metric")
VALUE_FIELDS = frozenset({"amount", "unit", "baseline", "comparison"})
FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "password",
        "private_key",
        "raw_private_content",
        "raw_content",
        "raw_input",
        "raw_output",
        "input_data",
        "output_data",
    }
)


class OutcomeFeedbackError(ValueError):
    """Raised when outcome feedback is unsafe or inconsistent with its run."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _reject_forbidden(value: Any, path: str = "feedback") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise OutcomeFeedbackError(
                    f"forbidden raw or secret field: {path}.{key}"
                )
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _required_text(value: Any, field: str, *, max_length: int = 240) -> str:
    result = str(value or "").strip()
    if not result:
        raise OutcomeFeedbackError(f"missing required field: {field}")
    if len(result) > max_length:
        raise OutcomeFeedbackError(f"field is too long: {field}")
    return result


def _observed_at(value: Any) -> str:
    result = _required_text(value or _utc_now(), "observed_at", max_length=64)
    try:
        datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeFeedbackError("observed_at must be an ISO-8601 timestamp") from exc
    return result


def _scene_binding(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise OutcomeFeedbackError("scene_binding must be an object")
    missing = [
        field
        for field in SCENE_BINDING_FIELDS
        if not str(value.get(field) or "").strip()
    ]
    if missing:
        raise OutcomeFeedbackError(f"scene_binding missing fields: {missing}")
    return {
        field: _required_text(value[field], f"scene_binding.{field}")
        for field in SCENE_BINDING_FIELDS
    }


def _evidence_refs(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise OutcomeFeedbackError("evidence_refs must be a list")
    refs = [
        _required_text(item, "evidence_refs.item", max_length=500) for item in value
    ]
    if len(refs) > 20:
        raise OutcomeFeedbackError("evidence_refs must contain at most 20 items")
    return refs


def _value_summary(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise OutcomeFeedbackError("value must be an object")
    unknown = sorted(set(value) - VALUE_FIELDS)
    if unknown:
        raise OutcomeFeedbackError(f"value contains unsupported fields: {unknown}")
    result = dict(value)
    if "unit" in result:
        result["unit"] = _required_text(result["unit"], "value.unit", max_length=64)
    if "comparison" in result:
        result["comparison"] = _required_text(
            result["comparison"], "value.comparison", max_length=120
        )
    for field in ("amount", "baseline"):
        if field in result and not isinstance(result[field], (int, float)):
            raise OutcomeFeedbackError(f"value.{field} must be numeric")
    return result


def _normalise_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise OutcomeFeedbackError("feedback must be an object")
    _reject_forbidden(payload)
    if payload.get("schema") not in (None, OUTCOME_FEEDBACK_SCHEMA):
        raise OutcomeFeedbackError("unsupported outcome feedback schema")
    state = _required_text(
        payload.get("consumption_state"), "consumption_state", max_length=32
    )
    if state not in OUTCOME_FEEDBACK_STATES:
        raise OutcomeFeedbackError(f"unsupported consumption_state: {state}")
    result_ref = str(payload.get("result_ref") or "").strip()
    if len(result_ref) > 500:
        raise OutcomeFeedbackError("result_ref is too long")
    return {
        "workflow_run_id": _required_text(
            payload.get("workflow_run_id"), "workflow_run_id"
        ),
        "outcome_id": _required_text(payload.get("outcome_id"), "outcome_id"),
        "scene_binding": _scene_binding(payload.get("scene_binding")),
        "consumption_state": state,
        "consumer_ref": _required_text(payload.get("consumer_ref"), "consumer_ref"),
        "result_ref": result_ref,
        "evidence_refs": _evidence_refs(payload.get("evidence_refs")),
        "value": _value_summary(payload.get("value")),
        "observed_at": _observed_at(payload.get("observed_at")),
        "note_digest": _digest(str(payload.get("note") or ""))
        if str(payload.get("note") or "").strip()
        else "",
    }


def validate_outcome_feedback(record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("schema") != OUTCOME_FEEDBACK_SCHEMA:
        raise OutcomeFeedbackError("invalid outcome feedback schema")
    normalised = _normalise_payload(record)
    for field in ("feedback_id", "idempotency_key", "recorded_at", "actor"):
        _required_text(record.get(field), field, max_length=500)
    for field in (
        "workflow_run_id",
        "outcome_id",
        "scene_binding",
        "consumption_state",
        "consumer_ref",
        "result_ref",
        "evidence_refs",
        "value",
        "observed_at",
    ):
        if record.get(field) != normalised[field]:
            raise OutcomeFeedbackError(f"{field} mismatch")
    note_digest = str(record.get("note_digest") or "")
    if note_digest and (
        not note_digest.startswith("sha256:") or len(note_digest) != 71
    ):
        raise OutcomeFeedbackError("note_digest must be a sha256 digest")
    return dict(record)


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / OUTCOME_FEEDBACK_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def read_outcome_feedback(omo_dir: Path | str) -> list[dict[str, Any]]:
    """Read and validate all durable feedback records."""
    records = _log(Path(omo_dir)).read_all()
    return [validate_outcome_feedback(record) for record in records]


def record_outcome_feedback(
    omo_dir: Path | str,
    payload: Mapping[str, Any],
    *,
    actor: str = "cockpit",
) -> dict[str, Any]:
    """Record explicit result consumption without mutating Workflow Mesh state."""
    normalised = _normalise_payload(payload)
    actor = _required_text(actor, "actor", max_length=240)
    snapshot = WorkflowMeshStore(omo_dir).snapshot(normalised["workflow_run_id"])
    if snapshot.get("state") == "unknown":
        raise OutcomeFeedbackError("workflow run does not exist")
    if snapshot.get("state") not in ELIGIBLE_WORKFLOW_STATES:
        raise OutcomeFeedbackError("workflow run has no eligible outcome yet")
    if snapshot.get("scene_binding") != normalised["scene_binding"]:
        raise OutcomeFeedbackError("feedback scene_binding does not match WorkflowRun")

    identity = {
        key: normalised[key]
        for key in (
            "workflow_run_id",
            "outcome_id",
            "scene_binding",
            "consumption_state",
            "consumer_ref",
            "result_ref",
            "evidence_refs",
            "value",
        )
    }
    idempotency_key = f"outcome-feedback:{_digest(identity)}"
    record = {
        "schema": OUTCOME_FEEDBACK_SCHEMA,
        "feedback_id": idempotency_key,
        "idempotency_key": idempotency_key,
        **normalised,
        "recorded_at": _utc_now(),
        "actor": actor,
    }
    validate_outcome_feedback(record)
    log = _log(Path(omo_dir))
    for existing in log.read_all():
        if existing.get("idempotency_key") != idempotency_key:
            continue
        return {"status": "deduplicated", "feedback": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "feedback": record}


__all__ = [
    "ELIGIBLE_WORKFLOW_STATES",
    "OUTCOME_FEEDBACK_LOG",
    "OUTCOME_FEEDBACK_SCHEMA",
    "OUTCOME_FEEDBACK_STATES",
    "OutcomeFeedbackError",
    "read_outcome_feedback",
    "record_outcome_feedback",
    "validate_outcome_feedback",
]
