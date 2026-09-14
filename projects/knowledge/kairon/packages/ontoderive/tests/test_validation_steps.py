"""Tests for ontoderive.validation_steps — 4 validation pipeline steps.

Covers ValidateStep (single), BatchValidateStep (batch parallel/sequential),
EvolveStep (single), BatchEvolveStep (batch parallel/sequential).
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ontoderive.pipeline_models import (
    BatchItem,
    BatchResult,
    ProgressInfo,
    StepStatus,
)
from ontoderive.validation_steps import (
    BatchEvolveStep,
    BatchValidateStep,
    EvolveStep,
    ValidateStep,
)


@pytest.fixture
def progress() -> ProgressInfo:
    return ProgressInfo(step_name="test", current=0, total=0, message="")


# ── ValidateStep ────────────────────────────────────────────


class TestValidateStep:
    def test_init_default_threshold(self):
        step = ValidateStep()
        assert step.threshold == 90.0
        assert step.name == "validate"

    def test_init_custom_threshold(self):
        step = ValidateStep(threshold=75.0)
        assert step.threshold == 75.0

    def test_execute_no_alignment_report_fails(self, progress):
        step = ValidateStep()
        result = step.execute({}, progress)
        assert result.status == StepStatus.FAILED
        assert "缺少对齐报告" in result.error or "alignment_report" in result.error

    def test_execute_valid_alignment(self, progress):
        # Mock MetaValidateEngine
        mock_verification = MagicMock()
        mock_verification.is_valid = True
        mock_verification.confidence_score.score = 0.95
        mock_verification.false_positives = []
        mock_verification.false_negatives = []

        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_instance.verify_alignment_result.return_value = mock_verification
            mock_engine.return_value = mock_instance

            step = ValidateStep()
            context = {"alignment_report": MagicMock()}
            result = step.execute(context, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["verified"] is True
        assert result.output["confidence"] == 0.95
        assert "validation_result" in context

    def test_execute_invalid_alignment(self, progress):
        mock_verification = MagicMock()
        mock_verification.is_valid = False
        mock_verification.confidence_score.score = 0.5
        mock_verification.false_positives = [1, 2]
        mock_verification.false_negatives = [3]

        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_instance.verify_alignment_result.return_value = mock_verification
            mock_engine.return_value = mock_instance

            step = ValidateStep()
            context = {"alignment_report": MagicMock()}
            result = step.execute(context, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["verified"] is False
        assert result.output["false_positives"] == 2
        assert result.output["false_negatives"] == 1

    def test_execute_handles_missing_confidence_score(self, progress):
        mock_verification = MagicMock()
        mock_verification.is_valid = True
        mock_verification.confidence_score = None
        mock_verification.false_positives = None
        mock_verification.false_negatives = None

        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_instance.verify_alignment_result.return_value = mock_verification
            mock_engine.return_value = mock_instance

            step = ValidateStep()
            context = {"alignment_report": MagicMock()}
            result = step.execute(context, progress)
        assert result.output["confidence"] == 0  # default

    def test_execute_exception_caught(self, progress):
        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_instance.verify_alignment_result.side_effect = RuntimeError("validator broken")
            mock_engine.return_value = mock_instance

            step = ValidateStep()
            result = step.execute({"alignment_report": MagicMock()}, progress)
        assert result.status == StepStatus.FAILED
        assert "validator broken" in result.error


# ── BatchValidateStep ──────────────────────────────────────


def _make_batch_item(idx: int, has_result: bool = True) -> BatchItem:
    item = BatchItem(id=f"i{idx}", data={"q": f"q{idx}"})
    # Initialize these as instance attrs so source code can set them
    item.status = StepStatus.PENDING
    item.error = ""
    if has_result:
        item.result = MagicMock()
        item.result.is_valid = True
    return item


class TestBatchValidateStep:
    def test_init_defaults(self):
        items = [_make_batch_item(1)]
        step = BatchValidateStep(items=items)
        assert step.threshold == 90.0
        assert step.parallel is True
        assert step.max_workers == 4
        assert step.isolate_failures is True
        assert step.name == "batch_validate"

    def test_execute_all_valid(self, progress):
        items = [_make_batch_item(1), _make_batch_item(2), _make_batch_item(3)]
        step = BatchValidateStep(items=items)
        result = step.execute({}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["total"] == 3
        assert result.output["completed"] == 3
        assert result.output["failed"] == 0
        assert result.output["passed"] == 3
        assert result.output["pass_rate"] == 100.0

    def test_execute_sequential(self, progress):
        items = [_make_batch_item(1), _make_batch_item(2)]
        step = BatchValidateStep(items=items, parallel=False)
        with patch.object(BatchValidateStep, "_execute_parallel") as mock_par:
            with patch.object(BatchValidateStep, "_execute_sequential") as mock_seq:
                mock_seq.return_value = items
                result = step.execute({}, progress)
        # Sequential was called, parallel not
        mock_seq.assert_called_once()
        mock_par.assert_not_called()
        assert result.status == StepStatus.COMPLETED

    def test_execute_parallel(self, progress):
        items = [_make_batch_item(1)]
        step = BatchValidateStep(items=items, parallel=True)
        with patch.object(BatchValidateStep, "_execute_parallel") as mock_par:
            mock_par.return_value = items
            step.execute({}, progress)
        mock_par.assert_called_once()

    def test_execute_with_invalid_items(self, progress):
        items = [
            _make_batch_item(1, has_result=True),
            _make_batch_item(2, has_result=True),
            _make_batch_item(3, has_result=False),
        ]
        items[0].result.alignment_rate = 0.9
        items[1].result.alignment_rate = 0.5

        def verify(report):
            verification = MagicMock()
            verification.is_valid = report.alignment_rate >= 0.9
            return verification

        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_engine.return_value.verify_alignment_result.side_effect = verify
            step = BatchValidateStep(items=items, isolate_failures=False)
            result = step.execute({}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["total"] == 3
        assert result.output["passed"] == 1

    def test_execute_with_failure(self, progress):
        items = [_make_batch_item(1)]
        step = BatchValidateStep(items=items)
        with patch.object(BatchValidateStep, "_validate_single") as mock_v:
            mock_v.side_effect = RuntimeError("validate failed")
            result = step.execute({}, progress)
        # Isolate failures default True, so step completes but failed count=1
        assert result.status == StepStatus.COMPLETED
        assert result.output["failed"] == 1

    def test_execute_exception_caught(self, progress):
        items = [_make_batch_item(1)]
        step = BatchValidateStep(items=items, isolate_failures=False)
        with patch.object(BatchValidateStep, "_execute_parallel") as mock_par:
            mock_par.side_effect = ValueError("parallel broken")
            result = step.execute({}, progress)
        assert result.status == StepStatus.FAILED
        assert "parallel broken" in result.error

    def test_execute_stores_results_in_context(self, progress):
        items = [_make_batch_item(1)]
        step = BatchValidateStep(items=items)
        context: dict = {}
        with patch.object(BatchValidateStep, "_validate_single", side_effect=lambda x: x):
            step.execute(context, progress)
        assert "batch_validation_results" in context

    def test_pass_rate_zero_when_no_completed(self, progress):
        items = [_make_batch_item(1)]
        step = BatchValidateStep(items=items)
        with patch.object(BatchValidateStep, "_execute_parallel") as mock_par:
            mock_par.return_value = items
            items[0].status = StepStatus.FAILED
            items[0].result = None
            result = step.execute({}, progress)
        # pass_rate should handle 0 completed gracefully
        assert result.output["pass_rate"] == 0

    def test_execute_progress_updated(self, progress):
        items = [_make_batch_item(1), _make_batch_item(2)]
        step = BatchValidateStep(items=items)
        with patch.object(BatchValidateStep, "_validate_single", side_effect=lambda x: x):
            step.execute({}, progress)
        # progress.total should be set to len(items)
        assert progress.total == 2

    def test_execute_pass_rate_calculation(self, progress):
        items = [_make_batch_item(i) for i in range(4)]
        for index, item in enumerate(items):
            item.result.alignment_rate = 1.0 if index < 2 else 0.5

        def verify(report):
            verification = MagicMock()
            verification.is_valid = report.alignment_rate >= 0.9
            return verification

        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_engine.return_value.verify_alignment_result.side_effect = verify
            step = BatchValidateStep(items=items)
            result = step.execute({}, progress)
        assert result.output["passed"] == 2
        assert result.output["pass_rate"] == 50.0

    def test_isolate_failures_true_handles_failure(self, progress):
        items = [_make_batch_item(1)]
        step = BatchValidateStep(items=items, isolate_failures=True)
        with patch.object(BatchValidateStep, "_validate_single") as mock_v:
            mock_v.side_effect = ValueError("boom")
            result = step.execute({}, progress)
        # item is marked FAILED but step completes
        assert result.status == StepStatus.COMPLETED
        assert items[0].status == StepStatus.FAILED
        assert "boom" in items[0].error


class TestBatchValidateStepHelpers:
    def test_execute_parallel_uses_thread_pool(self):
        items = [_make_batch_item(1), _make_batch_item(2)]
        step = BatchValidateStep(items=items, max_workers=2)
        with patch.object(BatchValidateStep, "_validate_single", side_effect=lambda x: x):
            with patch("ontoderive.validation_steps.ThreadPoolExecutor") as mock_tpe:
                executor = mock_tpe.return_value.__enter__.return_value
                futures = []

                def submit(function, item):
                    future = MagicMock()
                    future.result.return_value = function(item)
                    futures.append(future)
                    return future

                executor.submit.side_effect = submit
                with patch("ontoderive.validation_steps.as_completed", side_effect=lambda mapping: list(mapping)):
                    results = step._execute_parallel()
        assert len(results) == 2

    def test_execute_sequential(self):
        items = [_make_batch_item(1), _make_batch_item(2)]
        step = BatchValidateStep(items=items)
        with patch.object(BatchValidateStep, "_validate_single", side_effect=lambda x: x):
            results = step._execute_sequential()
        assert results == items

    def test_validate_single_with_alignment_rate(self):
        item = _make_batch_item(1)
        item.result.alignment_rate = 0.9
        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_inst = MagicMock()
            mock_inst.verify_alignment_result.return_value = MagicMock()
            mock_engine.return_value = mock_inst
            step = BatchValidateStep(items=[item])
            step._validate_single(item)
        assert item.status == StepStatus.COMPLETED

    def test_validate_single_without_alignment_rate(self):
        item = BatchItem(id="x", data={})  # no result set
        with patch("ontoderive.validation_steps.MetaValidateEngine") as mock_engine:
            mock_engine.return_value = MagicMock()
            step = BatchValidateStep(items=[item])
            step._validate_single(item)
        assert item.status == StepStatus.SKIPPED
        assert "No alignment report" in item.error


# ── EvolveStep ─────────────────────────────────────────────


class TestEvolveStep:
    def test_init_defaults(self):
        step = EvolveStep()
        assert step.auto_apply is False
        assert step.name == "evolve"

    def test_execute_no_alignment_report_fails(self, progress):
        step = EvolveStep()
        result = step.execute({}, progress)
        assert result.status == StepStatus.FAILED
        assert "缺少对齐报告" in result.error or "alignment_report" in result.error

    def test_execute_generates_suggestions(self, progress):
        # Mock alignment report with issues
        issue1 = MagicMock()
        issue1.declaration_name = "Foo"
        issue1.category.value = "TYPE_MISMATCH"
        issue1.description = "Type wrong"
        issue2 = MagicMock()
        issue2.declaration_name = "Bar"
        issue2.category.value = "MISSING"
        issue2.description = "Missing field"
        report = MagicMock()
        report.issues = [issue1, issue2]

        with patch("ontoderive.validation_steps.MetaEvolveEngine") as mock_engine:
            mock_inst = MagicMock()
            mock_inst.generate_update_suggestion.side_effect = lambda *a: f"fix for {a[0]}"
            mock_engine.return_value = mock_inst

            step = EvolveStep()
            context = {"alignment_report": report}
            result = step.execute(context, progress)
        assert result.status == StepStatus.COMPLETED
        assert "evolve_suggestions" in context
        assert len(context["evolve_suggestions"]) == 2
        assert result.output["suggestions_count"] == 2
        assert result.output["auto_apply"] is False

    def test_execute_limits_to_10_issues(self, progress):
        report = MagicMock()
        report.issues = [
            MagicMock(declaration_name=f"x{i}", category=MagicMock(value="C"), description="d") for i in range(15)
        ]

        with patch("ontoderive.validation_steps.MetaEvolveEngine") as mock_engine:
            mock_inst = MagicMock()
            mock_inst.generate_update_suggestion.return_value = "fix"
            mock_engine.return_value = mock_inst

            step = EvolveStep()
            context = {"alignment_report": report}
            result = step.execute(context, progress)
        # 15 issues, only 10 processed
        assert result.output["suggestions_count"] == 10
        assert result.items_processed == 10
        assert len(context["evolve_suggestions"]) == 10

    def test_execute_no_suggestion_for_issue(self, progress):
        report = MagicMock()
        report.issues = [MagicMock(declaration_name="X", category=MagicMock(value="C"), description="d")]

        with patch("ontoderive.validation_steps.MetaEvolveEngine") as mock_engine:
            mock_inst = MagicMock()
            mock_inst.generate_update_suggestion.return_value = None  # no suggestion
            mock_engine.return_value = mock_inst

            step = EvolveStep()
            context = {"alignment_report": report}
            result = step.execute(context, progress)
        assert result.output["suggestions_count"] == 0

    def test_execute_exception_caught(self, progress):
        with patch("ontoderive.validation_steps.MetaEvolveEngine") as mock_engine:
            mock_inst = MagicMock()
            mock_inst.generate_update_suggestion.side_effect = RuntimeError("evolve broken")
            mock_engine.return_value = mock_inst

            report = MagicMock()
            report.issues = [MagicMock(declaration_name="X", category=MagicMock(value="C"), description="d")]
            step = EvolveStep()
            result = step.execute({"alignment_report": report}, progress)
        assert result.status == StepStatus.FAILED
        assert "evolve broken" in result.error

    def test_execute_auto_apply_output(self, progress):
        report = MagicMock()
        report.issues = []
        with patch("ontoderive.validation_steps.MetaEvolveEngine") as mock_engine:
            mock_engine.return_value = MagicMock()
            step = EvolveStep(auto_apply=True)
            context = {"alignment_report": report}
            result = step.execute(context, progress)
        assert result.output["auto_apply"] is True


# ── BatchEvolveStep ───────────────────────────────────────


class TestBatchEvolveStep:
    def test_init_defaults(self):
        items = [_make_batch_item(1)]
        step = BatchEvolveStep(items=items)
        assert step.auto_apply is False
        assert step.parallel is True
        assert step.max_workers == 4
        assert step.isolate_failures is True
        assert step.name == "batch_evolve"

    def test_execute_no_issues_generated(self, progress):
        report = MagicMock()
        report.issues = []
        items = [_make_batch_item(1)]
        # Make item.result expose an iterable `issues` list so _evolve_single
        # does not iterate a plain MagicMock (which raises on 3.13).
        items[0].result.issues = []
        step = BatchEvolveStep(items=items)
        context = {"alignment_report": report}
        result = step.execute(context, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output.total == 1
        assert result.output.completed == 1
        assert result.output.failed == 0

    def test_execute_sequential(self, progress):
        report = MagicMock()
        report.issues = []
        items = [_make_batch_item(1)]
        step = BatchEvolveStep(items=items, parallel=False)
        with patch.object(BatchEvolveStep, "_execute_parallel") as mock_par:
            with patch.object(BatchEvolveStep, "_execute_sequential") as mock_seq:
                mock_seq.return_value = items
                step.execute({"alignment_report": report}, progress)
        mock_seq.assert_called_once()
        mock_par.assert_not_called()

    def test_execute_with_failure(self, progress):
        report = MagicMock()
        report.issues = []
        items = [_make_batch_item(1)]
        step = BatchEvolveStep(items=items, isolate_failures=False)
        with patch.object(BatchEvolveStep, "_execute_parallel") as mock_par:
            mock_par.side_effect = ValueError("parallel broken")
            result = step.execute({"alignment_report": report}, progress)
        assert result.status == StepStatus.FAILED
        assert "parallel broken" in result.error

    def test_execute_exception_caught(self, progress):
        report = MagicMock()
        report.issues = []
        items = [_make_batch_item(1)]
        step = BatchEvolveStep(items=items)
        with patch.object(BatchEvolveStep, "_execute_parallel") as mock_par:
            mock_par.side_effect = OSError("io error")
            result = step.execute({"alignment_report": report}, progress)
        assert result.status == StepStatus.FAILED
        assert "io error" in result.error

    def test_execute_stores_results_in_context(self, progress):
        report = MagicMock()
        report.issues = []
        items = [_make_batch_item(1)]
        step = BatchEvolveStep(items=items)
        context: dict = {"alignment_report": report}
        with patch.object(BatchEvolveStep, "_evolve_single", side_effect=lambda x: x):
            step.execute(context, progress)
        assert "batch_evolve_results" in context

    def test_execute_output_is_batch_result_instance(self, progress):
        report = MagicMock()
        report.issues = []
        items = [_make_batch_item(1)]
        step = BatchEvolveStep(items=items)
        with patch.object(BatchEvolveStep, "_evolve_single", side_effect=lambda x: x):
            result = step.execute({"alignment_report": report}, progress)
        # output should be a BatchResult dataclass
        assert isinstance(result.output, BatchResult)

    def test_evolve_single_with_issues(self):
        item = BatchItem(id="x", data={})
        item.result = MagicMock()
        item.result.issues = [MagicMock(declaration_name="X", category=MagicMock(value="C"), description="d")]

        with patch("ontoderive.validation_steps.MetaEvolveEngine") as mock_engine:
            mock_inst = MagicMock()
            mock_inst.generate_update_suggestion.return_value = "fix"
            mock_engine.return_value = mock_inst
            step = BatchEvolveStep(items=[item])
            step._evolve_single(item)
        assert item.status == StepStatus.COMPLETED
        assert isinstance(item.result, list)

    def test_evolve_single_without_issues(self):
        item = BatchItem(id="x", data={})
        with patch("ontoderive.validation_steps.MetaEvolveEngine") as mock_engine:
            mock_engine.return_value = MagicMock()
            step = BatchEvolveStep(items=[item])
            step._evolve_single(item)
        assert item.status == StepStatus.SKIPPED
        assert "No alignment report" in item.error


# ── Common step integration ────────────────────────────


class TestStepCommonBehavior:
    def test_all_steps_inherit_from_pipeline_step(self):
        from ontoderive.pipeline_steps.base import PipelineStep

        for cls in (ValidateStep, BatchValidateStep, EvolveStep, BatchEvolveStep):
            assert issubclass(cls, PipelineStep)

    def test_all_steps_have_execute(self):
        for cls in (ValidateStep, BatchValidateStep, EvolveStep, BatchEvolveStep):
            assert hasattr(cls, "execute")
            assert callable(cls.execute)

    def test_all_steps_set_name_via_super(self):
        expected = {
            "validate": ValidateStep,
            "batch_validate": BatchValidateStep,
            "evolve": EvolveStep,
            "batch_evolve": BatchEvolveStep,
        }
        for expected_name, cls in expected.items():
            step = cls(items=[]) if "batch" in expected_name else cls()
            assert step.name == expected_name
