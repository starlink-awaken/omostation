"""Regression tests for the canonical 12-dimension architecture contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "architecture-check.py"
SPEC = importlib.util.spec_from_file_location("architecture_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
architecture_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(architecture_check)


OFFICIAL_DIMENSIONS = [
    "X1_audit",
    "X2_freshness",
    "X3_value",
    "X4_consistency",
    "D1_scene",
    "D2_function",
    "D3_journey",
    "D4_experience",
    "D5_vision",
    "D6_operations",
    "D7_maintenance",
    "D8_harness",
]


def _dimension_document(dimensions: list[str]) -> dict:
    return {
        "dimensions": {name: {} for name in dimensions},
        "measurement_framework": {"score_range": [0, 10], "target_score": 9.5},
    }


def test_official_twelve_dimensions_have_no_findings() -> None:
    errors, warnings = architecture_check.check_dimension_system(_dimension_document(OFFICIAL_DIMENSIONS))

    assert errors == []
    assert warnings == []


def test_missing_harness_dimension_is_an_error() -> None:
    errors, _warnings = architecture_check.check_dimension_system(_dimension_document(OFFICIAL_DIMENSIONS[:-1]))

    assert errors == ["dimensions 缺少业务维度 D8_harness"]


def test_budget_accepts_approximate_numeric_current() -> None:
    errors, warnings = architecture_check.check_anti_corrosion_budget(
        {"budgets": {"bin_scripts": {"max_count": 560, "current": "~400", "alert_threshold": 0.95}}}
    )

    assert errors == []
    assert warnings == []


def test_budget_rejects_non_numeric_values_without_crashing() -> None:
    errors, warnings = architecture_check.check_anti_corrosion_budget(
        {"budgets": {"bin_scripts": {"max_count": 560, "current": "unknown", "alert_threshold": 0.95}}}
    )

    assert errors == ["bin_scripts: current 必须是数值，实际为 'unknown'"]
    assert warnings == []


def test_budget_rejects_non_finite_and_out_of_range_values() -> None:
    non_finite_errors, _ = architecture_check.check_anti_corrosion_budget(
        {"budgets": {"bin_scripts": {"max_count": 560, "current": "nan", "alert_threshold": 0.95}}}
    )
    threshold_errors, _ = architecture_check.check_anti_corrosion_budget(
        {"budgets": {"bin_scripts": {"max_count": 560, "current": 400, "alert_threshold": 1.5}}}
    )

    assert non_finite_errors == ["bin_scripts: current 必须是数值，实际为 'nan'"]
    assert threshold_errors == ["bin_scripts: alert_threshold 必须在 0 到 1 之间，实际为 1.5"]


def test_live_harness_entry_proves_agent_workflow_delegation() -> None:
    errors, warnings = architecture_check.check_harness_policy()

    assert errors == []
    assert "harness run 应内部调用 agent-workflow" not in warnings


def test_gate_and_strict_warning_exit_policy() -> None:
    budget_advisory = "governance_rules: 当前 81 接近预算 85 (阈值 90%)"
    assert architecture_check.result_exit_code([], [budget_advisory], gate=True, strict=False) == 0
    assert architecture_check.result_exit_code([], ["structural warning"], gate=True, strict=False) == 1
    assert architecture_check.result_exit_code([], [budget_advisory], gate=False, strict=True) == 1
    assert architecture_check.result_exit_code(["error"], [], gate=True, strict=False) == 1
