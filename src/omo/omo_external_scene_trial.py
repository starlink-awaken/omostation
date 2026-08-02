"""Governed, proposal-only contracts for an external scene trial.

The trial contract binds a real consumer and measurable outcome to an already
validated Scene Card, but deliberately stops before admission or execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog, fcntl_lock

TRIAL_SCHEMA = "external-scene-trial/v1"
TRIAL_LOG = Path("_knowledge/workflow-mesh/external-scene-trials.jsonl")
_OPAQUE_PREFIXES = ("evidence://", "vault://redacted/", "ref://", "sample://")
_TRIAL_STAGES = frozenset({"observation_only"})
_TRIAL_STATUSES = frozenset({"proposal_only"})
_DIRECTIONS = frozenset({"increase", "decrease", "target", "binary"})
_FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "content",
        "cookie",
        "document_body",
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
        "token",
    }
)


class ExternalSceneTrialError(ValueError):
    """Raised when a scene trial is unsafe or incomplete."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _required_text(value: Any, field: str, *, max_length: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExternalSceneTrialError(f"missing required field: {field}")
    if len(text) > max_length:
        raise ExternalSceneTrialError(f"field is too long: {field}")
    return text


def _opaque(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if not text.startswith(_OPAQUE_PREFIXES):
        raise ExternalSceneTrialError(f"{field} must be an opaque reference")
    return text


def _refs(value: Any, field: str, *, minimum: int = 1, maximum: int = 20) -> list[str]:
    if not isinstance(value, list):
        raise ExternalSceneTrialError(f"{field} must be a list")
    refs = sorted({_opaque(item, f"{field}.item") for item in value})
    if not minimum <= len(refs) <= maximum:
        raise ExternalSceneTrialError(f"{field} must contain {minimum}-{maximum} references")
    return refs


def _timestamp(value: Any, field: str) -> str:
    text = _required_text(value, field, max_length=64)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalSceneTrialError(f"invalid timestamp: {field}") from exc
    return text


def _reject_forbidden(value: Any, path: str = "trial") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalSceneTrialError(f"forbidden raw or secret field: {path}.{key}")
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _scene_binding(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ExternalSceneTrialError("scene_binding must be an object")
    return {
        field: _required_text(value.get(field), f"scene_binding.{field}", max_length=240)
        for field in ("scene_id", "journey_id", "outcome_metric")
    }


def _metric(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalSceneTrialError("metric must be an object")
    unknown = set(value) - {"metric_id", "direction", "unit", "target", "baseline_ref", "measurement_ref"}
    if unknown:
        raise ExternalSceneTrialError(f"metric contains unsupported fields: {sorted(unknown)}")
    direction = _required_text(value.get("direction"), "metric.direction", max_length=32)
    if direction not in _DIRECTIONS:
        raise ExternalSceneTrialError(f"unsupported metric direction: {direction}")
    target = value.get("target")
    if target is not None and (isinstance(target, bool) or not isinstance(target, (int, float))):
        raise ExternalSceneTrialError("metric.target must be numeric")
    return {
        "metric_id": _required_text(value.get("metric_id"), "metric.metric_id", max_length=160),
        "direction": direction,
        "unit": _required_text(value.get("unit"), "metric.unit", max_length=64) if value.get("unit") else None,
        "target": target,
        "baseline_ref": _opaque(value.get("baseline_ref"), "metric.baseline_ref"),
        "measurement_ref": _opaque(value.get("measurement_ref"), "metric.measurement_ref"),
    }


def _sample_plan(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ExternalSceneTrialError("sample_plan must be an object")
    unknown = set(value) - {"minimum_samples", "window_seconds"}
    if unknown:
        raise ExternalSceneTrialError(f"sample_plan contains unsupported fields: {sorted(unknown)}")
    samples = value.get("minimum_samples")
    window = value.get("window_seconds")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 1 <= samples <= 10000:
        raise ExternalSceneTrialError("sample_plan.minimum_samples must be 1-10000")
    if isinstance(window, bool) or not isinstance(window, int) or not 1 <= window <= 31536000:
        raise ExternalSceneTrialError("sample_plan.window_seconds must be 1-31536000")
    return {"minimum_samples": samples, "window_seconds": window}


def _feedback_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalSceneTrialError("feedback_contract must be an object")
    if value.get("schema") != "outcome-feedback/v1":
        raise ExternalSceneTrialError("feedback_contract must use outcome-feedback/v1")
    return {
        "schema": "outcome-feedback/v1",
        "required_workflow_run_id": True,
        "required_evidence_refs": True,
        "allowed_consumption_states": ["reviewed", "adopted", "rejected"],
        "closure_is_not_success": True,
    }


def _normalise(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ExternalSceneTrialError("trial must be an object")
    _reject_forbidden(payload)
    allowed = {
        "schema",
        "trial_id",
        "scene_binding",
        "consumer_ref",
        "owner_ref",
        "approver_ref",
        "permission_ref",
        "evidence_refs",
        "preflight_ref",
        "catalog_observation_id",
        "trial_stage",
        "status",
        "metric",
        "sample_plan",
        "rollback_ref",
        "activation",
        "provider_invocation",
        "workflow_run_id",
        "feedback_contract",
        "actor",
        "source_ref",
        "observed_at",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ExternalSceneTrialError(f"trial contains unsupported fields: {sorted(unknown)}")
    if payload.get("schema") != TRIAL_SCHEMA:
        raise ExternalSceneTrialError("unexpected trial schema")
    if payload.get("activation") != "forbidden":
        raise ExternalSceneTrialError("trial activation must be forbidden")
    if payload.get("provider_invocation") is not False:
        raise ExternalSceneTrialError("provider invocation must be false")
    if payload.get("workflow_run_id") not in (None, ""):
        raise ExternalSceneTrialError("trial cannot bind a WorkflowRun before promotion")
    stage = _required_text(payload.get("trial_stage"), "trial_stage", max_length=32)
    if stage not in _TRIAL_STAGES:
        raise ExternalSceneTrialError(f"unsupported trial stage: {stage}")
    status = _required_text(payload.get("status"), "status", max_length=32)
    if status not in _TRIAL_STATUSES:
        raise ExternalSceneTrialError(f"unsupported trial status: {status}")
    return {
        "schema": TRIAL_SCHEMA,
        "trial_id": _required_text(payload.get("trial_id"), "trial_id", max_length=240),
        "scene_binding": _scene_binding(payload.get("scene_binding")),
        "consumer_ref": _opaque(payload.get("consumer_ref"), "consumer_ref"),
        "owner_ref": _opaque(payload.get("owner_ref"), "owner_ref"),
        "approver_ref": _opaque(payload.get("approver_ref"), "approver_ref"),
        "permission_ref": _opaque(payload.get("permission_ref"), "permission_ref"),
        "evidence_refs": _refs(payload.get("evidence_refs"), "evidence_refs", minimum=2),
        "preflight_ref": _opaque(payload.get("preflight_ref"), "preflight_ref"),
        "catalog_observation_id": _required_text(payload.get("catalog_observation_id"), "catalog_observation_id", max_length=240),
        "trial_stage": stage,
        "status": status,
        "metric": _metric(payload.get("metric")),
        "sample_plan": _sample_plan(payload.get("sample_plan")),
        "rollback_ref": _opaque(payload.get("rollback_ref"), "rollback_ref"),
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "feedback_contract": _feedback_contract(payload.get("feedback_contract")),
        "actor": _required_text(payload.get("actor") or "scene-trial", "actor", max_length=240),
        "source_ref": _required_text(payload.get("source_ref") or "omo:external-resources:scene-trial", "source_ref"),
        "observed_at": _timestamp(payload.get("observed_at"), "observed_at"),
    }


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / TRIAL_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def _contract_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: nested
        for key, nested in value.items()
        if key
        not in {
            "actor",
            "source_ref",
            "observed_at",
            "recorded_at",
            "trial_receipt_id",
            "trial_digest",
        }
    }


def read_external_scene_trials(omo_dir: Path | str) -> list[dict[str, Any]]:
    return [dict(record) for record in _log(Path(omo_dir)).read_all()]


def record_external_scene_trial(omo_dir: Path | str, payload: Mapping[str, Any]) -> dict[str, Any]:
    normalised = _normalise(payload)
    contract_identity = _contract_identity(normalised)
    trial_digest = _digest(contract_identity)
    receipt_id = f"external-scene-trial:{hashlib.sha256(normalised['trial_id'].encode()).hexdigest()[:32]}"
    record = {
        **normalised,
        "trial_receipt_id": receipt_id,
        "trial_digest": trial_digest,
        "recorded_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    log = _log(Path(omo_dir))
    for existing in log.read_all():
        if existing.get("trial_receipt_id") != receipt_id:
            continue
        existing_digest = _digest(_contract_identity(existing))
        if existing.get("trial_digest") != trial_digest and existing_digest != trial_digest:
            raise ExternalSceneTrialError("conflicting duplicate trial_id")
        return {"status": "deduplicated", "receipt": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "receipt": record}


__all__ = [
    "TRIAL_LOG",
    "TRIAL_SCHEMA",
    "ExternalSceneTrialError",
    "read_external_scene_trials",
    "record_external_scene_trial",
]
