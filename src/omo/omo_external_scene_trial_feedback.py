"""Governed, proposal-only review receipts for external scene trials."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_external_scene_trial import (
    _digest,
    _opaque,
    _refs,
    _required_text,
    _timestamp,
    read_external_scene_trials,
)
from omo.omo_io import AppendOnlyLog, fcntl_lock

FEEDBACK_SCHEMA = "external-scene-trial-feedback/v1"
FEEDBACK_LOG = Path("_knowledge/workflow-mesh/external-scene-trial-feedback.jsonl")
_REVIEW_ACTIONS = frozenset({"continue", "request_changes", "reject"})
_MUTABLE_FIELDS = frozenset(
    {
        "actor",
        "source_ref",
        "observed_at",
        "recorded_at",
        "feedback_receipt_id",
        "feedback_digest",
    }
)
_FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "password",
        "private_key",
        "raw_content",
        "raw_input",
        "raw_output",
        "sample_data",
        "input_data",
        "output_data",
        "note",
        "rationale",
    }
)


class ExternalSceneTrialFeedbackError(ValueError):
    """Raised when a trial review receipt is not safe or well-formed."""


def _reject_forbidden(value: Any, path: str = "feedback") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalSceneTrialFeedbackError(
                    f"forbidden raw or secret field: {path}.{key}"
                )
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / FEEDBACK_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def _contract_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: nested for key, nested in value.items() if key not in _MUTABLE_FIELDS}


def _normalise(payload: Mapping[str, Any], omo_dir: Path) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ExternalSceneTrialFeedbackError("feedback must be an object")
    _reject_forbidden(payload)
    allowed = {
        "schema",
        "feedback_id",
        "trial_id",
        "review_action",
        "evidence_refs",
        "reviewer_ref",
        "review_ref",
        "activation",
        "provider_invocation",
        "workflow_run_id",
        "actor",
        "source_ref",
        "observed_at",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ExternalSceneTrialFeedbackError(
            f"feedback contains unsupported fields: {sorted(unknown)}"
        )
    if payload.get("schema") != FEEDBACK_SCHEMA:
        raise ExternalSceneTrialFeedbackError("unexpected feedback schema")
    trial_id = _required_text(payload.get("trial_id"), "trial_id", max_length=240)
    trials = read_external_scene_trials(omo_dir)
    trial = next((item for item in trials if item.get("trial_id") == trial_id), None)
    if trial is None:
        raise ExternalSceneTrialFeedbackError(
            "trial_id does not reference a recorded scene trial"
        )
    if (
        trial.get("trial_stage") != "observation_only"
        or trial.get("status") != "proposal_only"
    ):
        raise ExternalSceneTrialFeedbackError(
            "only proposal-only observation trials accept review feedback"
        )
    if payload.get("activation") != "forbidden":
        raise ExternalSceneTrialFeedbackError("feedback activation must be forbidden")
    if payload.get("provider_invocation") is not False:
        raise ExternalSceneTrialFeedbackError(
            "feedback provider invocation must be false"
        )
    if payload.get("workflow_run_id") not in (None, ""):
        raise ExternalSceneTrialFeedbackError(
            "trial review feedback cannot bind a WorkflowRun"
        )
    action = _required_text(
        payload.get("review_action"), "review_action", max_length=32
    )
    if action not in _REVIEW_ACTIONS:
        raise ExternalSceneTrialFeedbackError(f"unsupported review_action: {action}")
    return {
        "schema": FEEDBACK_SCHEMA,
        "feedback_id": _required_text(
            payload.get("feedback_id"), "feedback_id", max_length=240
        ),
        "trial_id": trial_id,
        "review_action": action,
        "evidence_refs": _refs(
            payload.get("evidence_refs"), "evidence_refs", minimum=1
        ),
        "reviewer_ref": _opaque(payload.get("reviewer_ref"), "reviewer_ref"),
        "review_ref": _opaque(payload.get("review_ref"), "review_ref"),
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "actor": _required_text(payload.get("actor") or "scene-trial-review", "actor"),
        "source_ref": _required_text(
            payload.get("source_ref")
            or "cockpit:external-resources:scene-trial-review",
            "source_ref",
        ),
        "observed_at": _timestamp(payload.get("observed_at"), "observed_at"),
    }


def read_external_scene_trial_feedback(omo_dir: Path | str) -> list[dict[str, Any]]:
    return [dict(record) for record in _log(Path(omo_dir)).read_all()]


def record_external_scene_trial_feedback(
    omo_dir: Path | str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    root = Path(omo_dir)
    normalised = _normalise(payload, root)
    digest = _digest(_contract_identity(normalised))
    receipt_id = f"external-scene-trial-feedback:{hashlib.sha256(normalised['feedback_id'].encode()).hexdigest()[:32]}"
    record = {
        **normalised,
        "feedback_receipt_id": receipt_id,
        "feedback_digest": digest,
        "recorded_at": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    log = _log(root)
    for existing in log.read_all():
        if existing.get("feedback_receipt_id") != receipt_id:
            continue
        existing_digest = _digest(_contract_identity(existing))
        if existing.get("feedback_digest") != digest and existing_digest != digest:
            raise ExternalSceneTrialFeedbackError("conflicting duplicate feedback_id")
        return {"status": "deduplicated", "feedback": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "feedback": record}


__all__ = [
    "FEEDBACK_LOG",
    "FEEDBACK_SCHEMA",
    "ExternalSceneTrialFeedbackError",
    "read_external_scene_trial_feedback",
    "record_external_scene_trial_feedback",
]
