from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# pyright: reportAttributeAccessIssue=false
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Validation Steps ≡ Module
# 内涵 ≝ {Validation, Steps}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ValidationSteps)}
# 功能 ⊢ {Validation_Steps, Init_Validation, Validate_Steps}
# =============================================================================

# ---
# domain: D-Logos
# layer: organ
# status: active
# ---

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..meta_evolve import MetaEvolveEngine
from ..meta_validate import MetaValidateEngine
from ..pipeline_models import (
    BatchItem,
    BatchResult,
    ProgressInfo,
    StepResult,
    StepStatus,
)
from .base import PipelineStep


class ValidateStep(PipelineStep):
    """验证步骤 - 使用 MetaValidateEngine 验证结果"""

    def __init__(self, threshold: float = 90.0) -> None:
        super().__init__("validate")
        self.threshold = threshold

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        try:
            alignment_report = context.get("alignment_report")

            if not alignment_report:
                raise ValueError("缺少对齐报告，请先执行 AlignStep")

            # 使用 MetaValidateEngine 验证
            validator = MetaValidateEngine()
            verification = validator.verify_alignment_result(alignment_report)

            # 更新上下文
            context["validation_result"] = verification

            result.status = StepStatus.COMPLETED
            result.output = {
                "verified": verification.is_valid,
                "confidence": verification.confidence_score.score if verification.confidence_score else 0,
                "false_positives": len(verification.false_positives) if verification.false_positives else 0,
                "false_negatives": len(verification.false_negatives) if verification.false_negatives else 0,
            }
            result.items_processed = 1

        except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result


class BatchValidateStep(PipelineStep):
    """批量验证步骤"""

    def __init__(
        self,
        items: list[BatchItem],
        threshold: float = 90.0,
        parallel: bool = True,
        max_workers: int = 4,
        isolate_failures: bool = True,
    ) -> None:
        super().__init__("batch_validate")
        self.items = items
        self.threshold = threshold
        self.parallel = parallel
        self.max_workers = max_workers
        self.isolate_failures = isolate_failures

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        progress.total = len(self.items)
        results = []

        try:
            if self.parallel:
                results = self._execute_parallel()
            else:
                results = self._execute_sequential()

            # 统计结果
            completed = sum(1 for r in results if r.status == StepStatus.COMPLETED)
            failed = sum(1 for r in results if r.status == StepStatus.FAILED)
            passed = sum(1 for r in results if r.result and hasattr(r.result, "is_valid") and r.result.is_valid)

            result.items_processed = completed
            result.items_failed = failed
            result.status = StepStatus.COMPLETED
            result.output = {
                "total": len(self.items),
                "completed": completed,
                "failed": failed,
                "passed": passed,
                "pass_rate": (passed / completed * 100) if completed > 0 else 0,
            }

            context["batch_validation_results"] = results

        except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result

    def _execute_parallel(self) -> list[BatchItem]:
        """并行执行验证"""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(self._validate_single, item): item for item in self.items}

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    validated_item = future.result()
                    results.append(validated_item)
                except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
                    if self.isolate_failures:
                        item.status = StepStatus.FAILED
                        item.error = str(e)
                        results.append(item)
                    else:
                        raise

        return results

    def _execute_sequential(self) -> list[BatchItem]:
        """顺序执行验证"""
        results = []
        for item in self.items:
            try:
                validated_item = self._validate_single(item)
                results.append(validated_item)
            except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
                if self.isolate_failures:
                    item.status = StepStatus.FAILED
                    item.error = str(e)
                    results.append(item)
                else:
                    raise
        return results

    def _validate_single(self, item: BatchItem) -> BatchItem:
        """验证单个项目"""
        item.status = StepStatus.RUNNING

        if item.result and hasattr(item.result, "alignment_rate"):
            validator = MetaValidateEngine()
            verification = validator.verify_alignment_result(item.result)
            item.result = verification
        else:
            item.status = StepStatus.SKIPPED
            item.error = "No alignment report to validate"

        item.status = StepStatus.COMPLETED
        return item


class EvolveStep(PipelineStep):
    """演化步骤 - 使用 MetaEvolveEngine 更新文档"""

    def __init__(self, auto_apply: bool = False) -> None:
        super().__init__("evolve")
        self.auto_apply = auto_apply

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        try:
            alignment_report = context.get("alignment_report")

            if not alignment_report:
                raise ValueError("缺少对齐报告，请先执行 AlignStep")

            # 使用 MetaEvolveEngine 分析并生成更新建议
            evolver = MetaEvolveEngine()

            # 为每个问题生成更新建议
            suggestions = []
            for issue in alignment_report.issues[:10]:  # 最多处理10个
                suggestion = evolver.generate_update_suggestion(  # type: ignore[attr-defined]
                    issue.declaration_name,
                    issue.category.value,
                    issue.description,
                )
                if suggestion:
                    suggestions.append(suggestion)

            # 更新上下文
            context["evolve_suggestions"] = suggestions

            result.status = StepStatus.COMPLETED
            result.output = {
                "suggestions_count": len(suggestions),
                "auto_apply": self.auto_apply,
            }
            result.items_processed = len(suggestions)

        except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result


class BatchEvolveStep(PipelineStep):
    """批量演化步骤"""

    def __init__(
        self,
        items: list[BatchItem],
        auto_apply: bool = False,
        parallel: bool = True,
        max_workers: int = 4,
        isolate_failures: bool = True,
    ) -> None:
        super().__init__("batch_evolve")
        self.items = items
        self.auto_apply = auto_apply
        self.parallel = parallel
        self.max_workers = max_workers
        self.isolate_failures = isolate_failures

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        progress.total = len(self.items)
        results = []

        try:
            if self.parallel:
                results = self._execute_parallel()
            else:
                results = self._execute_sequential()

            # 统计结果
            completed = sum(1 for r in results if r.status == StepStatus.COMPLETED)
            failed = sum(1 for r in results if r.status == StepStatus.FAILED)

            result.items_processed = completed
            result.items_failed = failed
            result.status = StepStatus.COMPLETED
            result.output = BatchResult(
                total=len(self.items),
                completed=completed,
                failed=failed,
                skipped=0,
                results=results,
                duration=time.time() - start_time,
            )

            context["batch_evolve_results"] = results

        except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result

    def _execute_parallel(self) -> list[BatchItem]:
        """并行执行演化"""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(self._evolve_single, item): item for item in self.items}

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    evolved_item = future.result()
                    results.append(evolved_item)
                except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
                    if self.isolate_failures:
                        item.status = StepStatus.FAILED
                        item.error = str(e)
                        results.append(item)
                    else:
                        raise

        return results

    def _execute_sequential(self) -> list[BatchItem]:
        """顺序执行演化"""
        results = []
        for item in self.items:
            try:
                evolved_item = self._evolve_single(item)
                results.append(evolved_item)
            except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
                if self.isolate_failures:
                    item.status = StepStatus.FAILED
                    item.error = str(e)
                    results.append(item)
                else:
                    raise
        return results

    def _evolve_single(self, item: BatchItem) -> BatchItem:
        """演化单个项目"""
        item.status = StepStatus.RUNNING

        if item.result and hasattr(item.result, "issues"):
            evolver = MetaEvolveEngine()
            suggestions = []

            for issue in item.result.issues[:5]:
                suggestion = evolver.generate_update_suggestion(  # type: ignore[attr-defined]
                    issue.declaration_name,
                    issue.category.value,
                    issue.description,
                )
                if suggestion:
                    suggestions.append(suggestion)

            item.result = suggestions
        else:
            item.status = StepStatus.SKIPPED
            item.error = "No alignment report to evolve"

        item.status = StepStatus.COMPLETED
        return item
