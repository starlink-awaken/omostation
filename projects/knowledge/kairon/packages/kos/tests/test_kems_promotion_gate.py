import pytest
from kos.kems import PromotionGateInputError, build_model_promotion_gate


def report(
    *,
    status: str = "shadow_pass",
    relative_improvement: float = 0.2,
    report_id: str = "report-1",
    model_mae: float = 8.0,
) -> dict[str, object]:
    return {
        "schema_version": "kems.model-acceptance.v1",
        "candidate_model_id": "candidate-v1",
        "baseline_model_id": "naive-last-v1",
        "status": status,
        "promotion": "blocked_until_omo_approval",
        "model_mae": model_mae,
        "baseline_mae": 10.0,
        "relative_improvement": relative_improvement,
        "observation_count": 10,
        "dataset_id": "kems-real",
        "dataset_version": "v1",
        "evaluation_manifest_sha256": "a" * 64,
        "report_id": report_id,
    }


def test_repeated_manifest_bound_shadow_reports_are_human_approval_eligible() -> None:
    result = build_model_promotion_gate(
        [report(report_id="report-1"), report(report_id="report-2")],
        candidate_model_id="candidate-v1",
        min_runs=2,
        min_observations=15,
        min_relative_improvement=0.1,
    )

    assert result["schema_version"] == "kems.model-promotion-gate.v1"
    assert result["status"] == "eligible_for_human_approval"
    assert result["promotion"] == "blocked_until_omo_approval"
    assert result["automatic_promotion"] is False
    assert result["summary"] == {
        "run_count": 2,
        "stable_pass_count": 2,
        "observation_count": 20,
        "model_mae": 8.0,
        "baseline_mae": 10.0,
        "relative_improvement": 0.2,
    }
    assert len(result["evidence"]["report_digests"]) == 2  # type: ignore[index]


def test_gate_blocks_unstable_runs_and_mismatched_manifest() -> None:
    second = report(status="needs_review", relative_improvement=-0.1, report_id="report-2", model_mae=14.0)
    second["evaluation_manifest_sha256"] = "b" * 64

    result = build_model_promotion_gate([report(), second], candidate_model_id="candidate-v1", min_runs=2)

    assert result["status"] == "blocked"
    assert result["promotion"] == "blocked_until_omo_approval"
    assert result["reason_codes"] == [
        "aggregate_improvement_below_threshold",
        "evaluation_manifest_sha256_mismatch",
        "relative_improvement_inconsistent",
        "run_improvement_below_threshold",
        "run_not_shadow_pass",
    ]


def test_gate_requires_manifest_binding_and_rejects_raw_report_fields() -> None:
    unbound = report()
    unbound.pop("evaluation_manifest_sha256")
    with pytest.raises(PromotionGateInputError, match="model_output"):
        build_model_promotion_gate([{**unbound, "model_output": "private"}], candidate_model_id="candidate-v1")

    result = build_model_promotion_gate(
        [unbound, {**unbound, "report_id": "report-2"}], candidate_model_id="candidate-v1"
    )
    assert result["status"] == "blocked"
    assert result["reason_codes"] == ["manifest_binding_required"]


def test_gate_rejects_duplicate_reports_and_invalid_thresholds() -> None:
    result = build_model_promotion_gate(
        [report(), report()],
        candidate_model_id="candidate-v1",
        min_runs=3,
    )
    assert result["status"] == "blocked"
    assert result["reason_codes"] == [
        "duplicate_shadow_report",
        "minimum_shadow_runs_not_met",
    ]

    with pytest.raises(PromotionGateInputError, match="invalid promotion gate thresholds"):
        build_model_promotion_gate([report()], candidate_model_id="candidate-v1", min_relative_improvement=1.0)
