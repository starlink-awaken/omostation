"""Governed persistence for safe external-resource selection evaluations.

The evaluation result is an observation, not a WorkflowRun transition and not
an execution receipt. OMO owns the append-only record so later evaluation can
join a selection with an actual receipt and explicit outcome feedback.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog, fcntl_lock

SOURCE_EVALUATION_SCHEMA = "external-resource-evaluation/v1"
OBSERVATION_SCHEMA = "external-resource-evaluation-observation/v1"
EVALUATION_LOG = Path("_knowledge/workflow-mesh/external-resource-evaluations.jsonl")

_FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "content",
        "cookie",
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
_SCENE_FIELDS = frozenset(
    {"scene_id", "journey_id", "outcome_metric", "data_scope", "operator", "permission_ref"}
)
_CANDIDATE_FIELDS = frozenset(
    {
        "resource_id",
        "capability",
        "status",
        "reasons",
        "decision_factors",
        "rank",
        "availability",
        "provenance_ref",
    }
)


class ExternalResourceEvaluationError(ValueError):
    """Raised when an evaluation observation is unsafe or malformed."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required_text(value: Any, field: str, *, max_length: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExternalResourceEvaluationError(f"missing required field: {field}")
    if len(text) > max_length:
        raise ExternalResourceEvaluationError(f"field is too long: {field}")
    return text


def _timestamp(value: Any, field: str = "observed_at") -> str:
    text = _required_text(value, field, max_length=64)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalResourceEvaluationError(f"invalid timestamp: {field}") from exc
    return text


def _reject_forbidden(value: Any, path: str = "evaluation") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalResourceEvaluationError(
                    f"forbidden raw or secret field: {path}.{key}"
                )
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _scalar(value: Any, field: str) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ExternalResourceEvaluationError(f"{field} must contain scalar values")


def _scene_binding(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ExternalResourceEvaluationError("scene_binding must be an object")
    missing = [field for field in ("scene_id", "journey_id", "outcome_metric") if not str(value.get(field) or "").strip()]
    if missing:
        raise ExternalResourceEvaluationError(f"scene_binding missing fields: {missing}")
    unknown = set(value) - _SCENE_FIELDS
    if unknown:
        raise ExternalResourceEvaluationError(
            f"scene_binding contains unsupported fields: {sorted(unknown)}"
        )
    return {
        str(key): _required_text(nested, f"scene_binding.{key}")
        for key, nested in value.items()
    }


def _candidate(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalResourceEvaluationError(f"candidate[{index}] must be an object")
    unknown = set(value) - _CANDIDATE_FIELDS
    if unknown:
        raise ExternalResourceEvaluationError(
            f"candidate[{index}] contains unsupported fields: {sorted(unknown)}"
        )
    reasons = value.get("reasons", [])
    if not isinstance(reasons, list) or len(reasons) > 64:
        raise ExternalResourceEvaluationError(f"candidate[{index}].reasons must be a list")
    factors = value.get("decision_factors", {})
    if not isinstance(factors, Mapping) or len(factors) > 32:
        raise ExternalResourceEvaluationError(
            f"candidate[{index}].decision_factors must be a bounded object"
        )
    rank = value.get("rank", [])
    if not isinstance(rank, list) or len(rank) > 16:
        raise ExternalResourceEvaluationError(f"candidate[{index}].rank must be a list")
    return {
        "resource_id": _required_text(value.get("resource_id"), f"candidate[{index}].resource_id"),
        "capability": _required_text(value.get("capability"), f"candidate[{index}].capability"),
        "status": _required_text(value.get("status"), f"candidate[{index}].status", max_length=64),
        "reasons": [_required_text(item, f"candidate[{index}].reasons.item", max_length=160) for item in reasons],
        "decision_factors": {
            _required_text(key, f"candidate[{index}].decision_factors.key", max_length=80): _scalar(
                nested, f"candidate[{index}].decision_factors"
            )
            for key, nested in factors.items()
        },
        "rank": [_scalar(item, f"candidate[{index}].rank") for item in rank],
        "availability": (
            _required_text(value["availability"], f"candidate[{index}].availability", max_length=64)
            if value.get("availability") is not None
            else None
        ),
        "provenance_ref": _required_text(
            value.get("provenance_ref"), f"candidate[{index}].provenance_ref"
        ),
    }


def _normalise_evaluation(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evaluation, Mapping):
        raise ExternalResourceEvaluationError("evaluation must be an object")
    _reject_forbidden(evaluation)
    allowed = {
        "schema",
        "mode",
        "activation",
        "raw_content_policy",
        "capability",
        "trace_id",
        "policy_digest",
        "scene_binding",
        "status",
        "selected_resource_id",
        "candidates",
        "reasons",
        "observed_at",
    }
    unknown = set(evaluation) - allowed
    if unknown:
        raise ExternalResourceEvaluationError(
            f"evaluation contains unsupported fields: {sorted(unknown)}"
        )
    if evaluation.get("schema") != SOURCE_EVALUATION_SCHEMA:
        raise ExternalResourceEvaluationError("unexpected evaluation schema")
    if evaluation.get("mode") != "read_only_evaluation":
        raise ExternalResourceEvaluationError("evaluation must be read_only_evaluation")
    if evaluation.get("activation") != "forbidden":
        raise ExternalResourceEvaluationError("evaluation activation must be forbidden")
    candidates = evaluation.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 500:
        raise ExternalResourceEvaluationError("evaluation candidates must be a bounded list")
    reasons = evaluation.get("reasons", [])
    if not isinstance(reasons, list) or len(reasons) > 64:
        raise ExternalResourceEvaluationError("evaluation reasons must be a list")
    selected = evaluation.get("selected_resource_id")
    selected_id = (
        _required_text(selected, "selected_resource_id", max_length=240)
        if selected is not None
        else None
    )
    normalised_candidates = [_candidate(item, index) for index, item in enumerate(candidates)]
    if selected_id and selected_id not in {item["resource_id"] for item in normalised_candidates}:
        raise ExternalResourceEvaluationError("selected_resource_id is not in candidates")
    summary = {
        "candidate_count": len(normalised_candidates),
        "eligible_count": sum(item["status"] == "eligible" for item in normalised_candidates),
        "rejected_count": sum(item["status"] == "rejected" for item in normalised_candidates),
        "not_applicable_count": sum(
            item["status"] == "not_applicable" for item in normalised_candidates
        ),
    }
    return {
        "schema": SOURCE_EVALUATION_SCHEMA,
        "mode": "read_only_evaluation",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "capability": _required_text(evaluation.get("capability"), "capability", max_length=160),
        "trace_id": _required_text(evaluation.get("trace_id"), "trace_id", max_length=240),
        "policy_digest": _required_text(evaluation.get("policy_digest"), "policy_digest"),
        "scene_binding": _scene_binding(evaluation.get("scene_binding")),
        "status": _required_text(evaluation.get("status"), "status", max_length=64),
        "selected_resource_id": selected_id,
        "candidates": normalised_candidates,
        "reasons": [_required_text(item, "evaluation.reasons.item", max_length=160) for item in reasons],
        "summary": summary,
    }


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / EVALUATION_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def read_external_resource_evaluations(omo_dir: Path | str) -> list[dict[str, Any]]:
    """Read validated, credential-free evaluation observations in append order."""
    records = _log(Path(omo_dir)).read_all()
    result: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ExternalResourceEvaluationError("evaluation log contains a non-object")
        result.append(dict(record))
    return result


def record_external_resource_evaluation(
    omo_dir: Path | str,
    evaluation: Mapping[str, Any],
    *,
    workflow_run_id: str | None = None,
    actor: str = "cockpit",
    source_ref: str = "omo:external-resources:evaluate",
    observed_at: str | None = None,
    evaluation_id: str | None = None,
) -> dict[str, Any]:
    """Persist one safe selection evaluation without mutating WorkflowRun."""
    normalised = _normalise_evaluation(evaluation)
    run_id = str(workflow_run_id or "").strip() or None
    if run_id is not None:
        run_id = _required_text(run_id, "workflow_run_id", max_length=240)
    actor = _required_text(actor or "cockpit", "actor", max_length=240)
    source_ref = _required_text(source_ref or "omo:external-resources:evaluate", "source_ref", max_length=500)
    observed = _timestamp(observed_at or evaluation.get("observed_at") or _utc_now())
    evaluation_digest = _digest(normalised)
    identity = {
        "workflow_run_id": run_id,
        "trace_id": normalised["trace_id"],
        "evaluation_digest": evaluation_digest,
    }
    derived_id = f"external-evaluation:{hashlib.sha256(_canonical(identity).encode('utf-8')).hexdigest()[:32]}"
    observation_id = _required_text(evaluation_id or derived_id, "evaluation_id", max_length=240)
    record = {
        **normalised,
        "schema": OBSERVATION_SCHEMA,
        "observation_id": observation_id,
        "evaluation_id": observation_id,
        "evaluation_digest": evaluation_digest,
        "observed_at": observed,
        "recorded_at": _utc_now(),
        "actor": actor,
        "source_ref": source_ref,
        "workflow_run_id": run_id,
    }
    log = _log(Path(omo_dir))
    for existing in log.read_all():
        if existing.get("evaluation_id") != observation_id:
            continue
        if existing.get("evaluation_digest") != evaluation_digest:
            raise ExternalResourceEvaluationError("conflicting duplicate evaluation_id")
        return {"status": "deduplicated", "observation": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "observation": record}


def read_latest_external_resource_evaluation(omo_dir: Path | str) -> dict[str, Any] | None:
    records = read_external_resource_evaluations(omo_dir)
    return records[-1] if records else None


__all__ = [
    "EVALUATION_LOG",
    "OBSERVATION_SCHEMA",
    "ExternalResourceEvaluationError",
    "read_external_resource_evaluations",
    "read_latest_external_resource_evaluation",
    "record_external_resource_evaluation",
]
