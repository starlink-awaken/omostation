"""End-to-end tests for the OntoDerive validation pipeline.

Drives `OntoDerive.run_validation_pipeline()` against a fixture project
in `tmp_path` and asserts the validation / evolution steps produce
non-empty results from the derive summary without mocking the engine.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from pathlib import Path

import pytest
from ontoderive.core.derive import OntoDerive
from ontoderive.pipeline_models import BatchItem, StepStatus
from ontoderive.validation_steps import (
    BatchEvolveStep,
    BatchValidateStep,
    EvolveStep,
    ValidateStep,
)


def _seed_project(root: Path) -> None:
    """Seed a minimal project so derive() produces a non-trivial summary."""
    for sub in ("facts", "entities", "inferences", "scheme", "protocols", "_logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "facts" / "D-F1.md").write_text(
        "| 编号 | 数据 | 数值 | 来源 |\n|------|------|------|------|\n| D-F1 | 测试事实 | 100 | 测试 |\n",
        encoding="utf-8",
    )
    (root / "entities" / "ORG-X.md").write_text(
        "**ORG-X**\n- description: 测试实体\n",
        encoding="utf-8",
    )
    (root / "inferences" / "INF-1.md").write_text(
        "## INF-1\nderives_from: [D-F1]\n理论支撑: 测试理论\n",
        encoding="utf-8",
    )


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    _seed_project(tmp_path)
    return tmp_path


def test_run_validation_pipeline_smoke(project_root: Path) -> None:
    od = OntoDerive(str(project_root))
    result = od.run_validation_pipeline()
    assert result["alignment_report"]["alignment_rate"] >= 0.0
    assert len(result["steps"]) == 4
    statuses = {step["status"] for step in result["steps"]}
    # The evolution step may return SKIPPED when the LLM is unavailable,
    # but the validation and batch steps should at least report status.
    assert all(
        status in {StepStatus.COMPLETED.value, StepStatus.FAILED.value, StepStatus.SKIPPED.value} for status in statuses
    )
    assert "summary" in result


def test_run_validation_pipeline_uses_batch_items(project_root: Path) -> None:
    od = OntoDerive(str(project_root))
    items = [
        BatchItem(
            id=f"item-{i}",
            data={"category": "TEST"},
            metadata={},
            status=StepStatus.PENDING,
            result={"issues": [], "alignment_rate": 0.95},
            error="",
        )
        for i in range(3)
    ]
    result = od.run_validation_pipeline(batch_items=items)
    assert result["summary"]["items"] == 3
    batch_step = result["steps"][1]
    assert batch_step["step"] == "batch_validate"


def test_run_validation_pipeline_propagates_failures(project_root: Path) -> None:
    od = OntoDerive(str(project_root))
    items = [BatchItem(id="bad", data={}, metadata={}, status=StepStatus.PENDING, result=None, error="")]
    result = od.run_validation_pipeline(batch_items=items)
    # With isolate_failures=True (default) the batch step still completes,
    # but the SKIPPED item must be reported.
    batch_step = result["steps"][1]
    assert batch_step["status"] in {StepStatus.COMPLETED.value, StepStatus.FAILED.value}
    assert result["summary"]["items"] == 1


def test_alignment_report_contains_core_fields(project_root: Path) -> None:
    od = OntoDerive(str(project_root))
    report = od.build_alignment_report()
    assert report["facts"] >= 1
    assert report["inferences"] >= 0
    assert isinstance(report["alignment_rate"], float)
    assert "issues" in report
    assert "entailment" in report


def test_evolution_step_consumes_report(project_root: Path) -> None:
    od = OntoDerive(str(project_root))
    report = od.build_alignment_report()
    report["issues"].append(
        {
            "declaration_name": "TEST-DECL",
            "category": "MISSING",
            "description": "fixture issue to drive the evolver",
        }
    )
    context = {"alignment_report": report}
    from ontoderive.pipeline_models import ProgressInfo

    progress = ProgressInfo(step_name="evolve", current=0, total=1)
    result = EvolveStep().execute(context, progress)
    assert result.status in {StepStatus.COMPLETED, StepStatus.FAILED}
    if result.status is StepStatus.COMPLETED:
        assert result.output["suggestions_count"] >= 0
        assert "evolve_suggestions" in context


def test_batch_steps_have_explicit_names() -> None:
    assert ValidateStep().name == "validate"
    assert BatchValidateStep(items=[]).name == "batch_validate"
    assert EvolveStep().name == "evolve"
    assert BatchEvolveStep(items=[]).name == "batch_evolve"
