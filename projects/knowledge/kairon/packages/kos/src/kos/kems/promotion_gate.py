"""Repeated shadow-evaluation gate for KEMS model promotion proposals."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SCHEMA = "kems.model-promotion-gate.v1"
_REQUIRED_BINDING_FIELDS = (
    "dataset_id",
    "dataset_version",
    "evaluation_manifest_sha256",
)
_FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text", "prompt", "model_output"}


class PromotionGateInputError(ValueError):
    """Raised when shadow reports cannot be safely compared."""


def _finite_number(value: object, field: str, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PromotionGateInputError(f"report {index}: {field} must be finite")
    return float(value)


def _report_digest(report: dict[str, Any]) -> str:
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _reject_forbidden(value: object, path: str = "report") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise PromotionGateInputError(f"{path}.{key} is forbidden")
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def build_model_promotion_gate(
    reports: object,
    *,
    candidate_model_id: str,
    min_runs: int = 2,
    min_observations: int = 1,
    min_relative_improvement: float = 0.0,
) -> dict[str, Any]:
    """Compare repeated manifest-bound shadow reports without authorizing promotion.

    A passing result is only an eligibility projection for a human/OMO review.
    It never changes a model registry, route, WorkflowRun or admission state.
    """
    candidate_model_id = candidate_model_id.strip()
    if not candidate_model_id:
        raise PromotionGateInputError("candidate_model_id is required")
    if min_runs <= 0 or min_observations <= 0 or not 0 <= min_relative_improvement < 1:
        raise PromotionGateInputError("invalid promotion gate thresholds")
    if not isinstance(reports, list) or not reports:
        raise PromotionGateInputError("reports must be a non-empty list")

    reason_codes: set[str] = set()
    report_digests: list[str] = []
    normalized: list[dict[str, Any]] = []
    binding_values: dict[str, str] = {}
    baseline_model_id: str | None = None
    model_total = 0.0
    baseline_total = 0.0
    observation_count = 0
    stable_pass_count = 0

    for index, raw_report in enumerate(reports, start=1):
        if not isinstance(raw_report, dict):
            raise PromotionGateInputError(f"report {index} must be an object")
        report = dict(raw_report)
        _reject_forbidden(report, f"report[{index}]")
        if report.get("schema_version") != "kems.model-acceptance.v1":
            raise PromotionGateInputError(f"report {index} has an unsupported schema")
        model_id = str(report.get("candidate_model_id") or "").strip()
        if model_id != candidate_model_id:
            reason_codes.add("candidate_model_mismatch")
        current_baseline = str(report.get("baseline_model_id") or "").strip()
        if not current_baseline:
            reason_codes.add("baseline_model_missing")
        elif baseline_model_id is None:
            baseline_model_id = current_baseline
        elif current_baseline != baseline_model_id:
            reason_codes.add("baseline_model_mismatch")

        for field in _REQUIRED_BINDING_FIELDS:
            value = str(report.get(field) or "").strip()
            if not value:
                reason_codes.add("manifest_binding_required")
            elif field not in binding_values:
                binding_values[field] = value
            elif binding_values[field] != value:
                reason_codes.add(f"{field}_mismatch")

        model_mae = _finite_number(report.get("model_mae"), "model_mae", index)
        baseline_mae = _finite_number(report.get("baseline_mae"), "baseline_mae", index)
        relative_improvement = _finite_number(report.get("relative_improvement"), "relative_improvement", index)
        observations = report.get("observation_count")
        if isinstance(observations, bool) or not isinstance(observations, int) or observations <= 0:
            raise PromotionGateInputError(f"report {index}: observation_count must be positive")
        if model_mae < 0 or baseline_mae < 0:
            raise PromotionGateInputError(f"report {index}: MAE cannot be negative")
        computed_improvement = (baseline_mae - model_mae) / baseline_mae if baseline_mae else 0.0
        if abs(relative_improvement - computed_improvement) > 1e-9:
            reason_codes.add("relative_improvement_inconsistent")
        if report.get("status") != "shadow_pass":
            reason_codes.add("run_not_shadow_pass")
        if report.get("promotion") != "blocked_until_omo_approval":
            reason_codes.add("promotion_boundary_invalid")
        if relative_improvement < min_relative_improvement:
            reason_codes.add("run_improvement_below_threshold")
        else:
            stable_pass_count += 1
        model_total += model_mae * observations
        baseline_total += baseline_mae * observations
        observation_count += observations
        report_digests.append(_report_digest(report))
        normalized.append(
            {
                "report_digest": report_digests[-1],
                "status": report.get("status"),
                "observation_count": observations,
                "relative_improvement": relative_improvement,
            }
        )

    if len(report_digests) != len(set(report_digests)):
        reason_codes.add("duplicate_shadow_report")
    if len(reports) < min_runs:
        reason_codes.add("minimum_shadow_runs_not_met")
    if observation_count < min_observations:
        reason_codes.add("minimum_observations_not_met")

    aggregate_model_mae = model_total / observation_count
    aggregate_baseline_mae = baseline_total / observation_count
    aggregate_relative_improvement = (
        (aggregate_baseline_mae - aggregate_model_mae) / aggregate_baseline_mae if aggregate_baseline_mae else 0.0
    )
    if aggregate_relative_improvement < min_relative_improvement:
        reason_codes.add("aggregate_improvement_below_threshold")

    eligible = not reason_codes
    payload: dict[str, Any] = {
        "schema_version": SCHEMA,
        "mode": "shadow_promotion_gate",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "automatic_promotion": False,
        "candidate_model_id": candidate_model_id,
        "baseline_model_id": baseline_model_id,
        "status": "eligible_for_human_approval" if eligible else "blocked",
        "promotion": "blocked_until_omo_approval",
        "reason_codes": sorted(reason_codes),
        "thresholds": {
            "min_runs": min_runs,
            "min_observations": min_observations,
            "min_relative_improvement": min_relative_improvement,
        },
        "runs": normalized,
        "summary": {
            "run_count": len(reports),
            "stable_pass_count": stable_pass_count,
            "observation_count": observation_count,
            "model_mae": aggregate_model_mae,
            "baseline_mae": aggregate_baseline_mae,
            "relative_improvement": aggregate_relative_improvement,
        },
        "evidence": {
            "dataset_id": binding_values.get("dataset_id"),
            "dataset_version": binding_values.get("dataset_version"),
            "evaluation_manifest_sha256": binding_values.get("evaluation_manifest_sha256"),
            "report_digests": report_digests,
        },
        "policy_boundary": {
            "side_effects": "disabled",
            "decision_owner": "human_or_omo",
            "registry_mutation": False,
            "route_mutation": False,
        },
    }
    return payload
