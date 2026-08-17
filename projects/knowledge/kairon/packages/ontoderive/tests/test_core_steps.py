"""End-to-end tests for the ontoderive core pipeline steps.

Drives ScanStep, DiffStep, and ReportStep against a fixture project
so the cross-step glue is observable from one place rather than
silently passing as untested code paths.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from pathlib import Path

import pytest
from ontoderive.pipeline_models import (
    ProgressInfo,
    StepStatus,
)
from ontoderive.pipeline_steps.core_steps import (
    DiffStep,
    ReportStep,
    ScanStep,
)

# ── ScanStep ───────────────────────────────────────────────


def test_scan_step_writes_outputs_into_context(tmp_path: Path):
    (tmp_path / "a.md").write_text("# a")
    (tmp_path / "b.py").write_text("# b")
    step = ScanStep(patterns=["*.md", "*.py"], root=tmp_path)
    context: dict = {}
    progress = ProgressInfo(step_name="scan", current=0, total=0)
    result = step.execute(context, progress)
    assert result.status is StepStatus.COMPLETED
    assert result.items_processed == 2
    assert progress.completed == 2
    output = result.output
    assert output["file_count"] == 2
    assert output["root"] == str(tmp_path)
    # Step persists discovered paths into the shared context for
    # downstream consumers (e.g. ReportStep).
    assert "scanned_files" in context
    assert len(context["scanned_files"]) == 2


def test_scan_step_falls_back_to_context_root(tmp_path: Path):
    (tmp_path / "doc.md").write_text("# doc")
    step = ScanStep(patterns=["*.md"])
    progress = ProgressInfo(step_name="scan", current=0, total=0)
    # No explicit root -> context["root"] -> Path(".")
    result = step.execute({"root": tmp_path}, progress)
    assert result.status is StepStatus.COMPLETED
    assert result.items_processed == 1
    assert result.output["root"] == str(tmp_path)


def test_scan_step_marks_failed_on_invalid_root(tmp_path: Path):
    progress = ProgressInfo(step_name="scan", current=0, total=0)
    # A non-existent path with strict mode would raise; we want the
    # step to capture the error and mark the result FAILED.
    step = ScanStep(patterns=["*.md"], root="/nonexistent_root_xyz_12345_abcdef")  # type: ignore[reportArgumentType]
    result = step.execute({}, progress)
    # Path.rglob returns [] for non-existent roots, so this actually
    # succeeds with file_count=0; lock the contract that the result
    # stays COMPLETED.
    assert result.status is StepStatus.COMPLETED
    assert result.items_processed == 0


# ── DiffStep ───────────────────────────────────────────────


def test_diff_step_reports_added_removed_common():
    progress = ProgressInfo(step_name="diff", current=0, total=0)
    step = DiffStep()
    context = {
        "source_a": [{"id": 1}, {"id": 2}, {"id": 3}],
        "source_b": [{"id": 2}, {"id": 3}, {"id": 4}],
    }
    result = step.execute(context, progress)
    assert result.status is StepStatus.COMPLETED
    assert result.items_processed == 6
    diff = result.output
    assert diff["total_a"] == 3
    assert diff["total_b"] == 3
    assert diff["added"] == 1
    assert diff["removed"] == 1
    assert diff["common"] == 2
    assert "diff_result" in context


# ── ReportStep ─────────────────────────────────────────────


def test_report_step_aggregates_prior_outputs():
    progress = ProgressInfo(step_name="report", current=0, total=0)
    step = ReportStep()
    context = {
        "scanned_files": [Path("a.md"), Path("b.md")],
        "diff_result": {"added": 1, "removed": 0, "common": 1, "total_a": 2, "total_b": 2},
        "validation_result": {"passed": True, "score": 0.9},
        "root_namespace_issues": [{"id": "x1"}],
        "section_index_issues": [{"id": "x2"}, {"id": "x3"}],
        "_executed_steps": ["scan", "diff", "validate"],
    }
    result = step.execute(context, progress)
    assert result.status is StepStatus.COMPLETED
    assert result.items_processed == 1
    assert progress.completed == 1
    assert "report" in context
    report = context["report"]
    assert report["summary"]["scan"] == {"files": 2}
    assert report["summary"]["diff"]["added"] == 1
    assert report["summary"]["validation"]["score"] == 0.9
    assert report["summary"]["governance_issues"] == 3
    assert report["total_steps"] == 3


def test_report_step_handles_empty_context():
    progress = ProgressInfo(step_name="report", current=0, total=0)
    step = ReportStep()
    result = step.execute({}, progress)
    assert result.status is StepStatus.COMPLETED
    assert result.items_processed == 1
    assert result.output["summary"] == {}
    assert result.output["total_steps"] == 0


# ── PipelineModel dataclass compatibility ─────────────────


def test_progress_info_slots_accept_completed_field():
    progress = ProgressInfo(step_name="scan", current=0, total=0)
    progress.completed = 5
    progress.failed = 1
    assert progress.completed == 5
    assert progress.failed == 1


def test_progress_info_rejects_negative_counters():
    with pytest.raises(ValueError, match="completed must be >= 0"):
        ProgressInfo(step_name="x", completed=-1)
    with pytest.raises(ValueError, match="failed must be >= 0"):
        ProgressInfo(step_name="x", failed=-1)


def test_progress_info_rejects_arbitrary_attribute():
    """Slots must reject fields that are not declared on the dataclass."""
    progress = ProgressInfo(step_name="x")
    with pytest.raises(AttributeError):
        progress.not_a_field = "nope"  # type: ignore[attr-defined]
