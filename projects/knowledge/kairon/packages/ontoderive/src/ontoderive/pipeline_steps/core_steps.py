"""Core pipeline steps — ScanStep, DiffStep, ReportStep.

Generic file/directory scanning, diff analysis, and report generation.
No external engine dependencies — self-contained pattern.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..pipeline_models import (
    ProgressInfo,
    StepResult,
    StepStatus,
)
from .base import PipelineStep


class ScanStep(PipelineStep):
    """Scan step — discover files matching patterns in a root directory.

    Outputs a list of discovered paths into ``context["scanned_files"]``.
    """

    def __init__(
        self,
        patterns: list[str] | None = None,
        root: Path | None = None,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> None:
        super().__init__("scan")
        self.patterns = patterns or ["*.py", "*.md", "*.yaml", "*.yml"]
        self.root = root
        self.parallel = parallel
        self.max_workers = max_workers

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        try:
            root = self.root or context.get("root", Path("."))
            root = Path(root)

            scanned_files: list[Path] = []
            for pattern in self.patterns:
                scanned_files.extend(sorted(root.rglob(pattern)))

            context["scanned_files"] = scanned_files
            result.status = StepStatus.COMPLETED
            result.output = {
                "file_count": len(scanned_files),
                "patterns": self.patterns,
                "root": str(root),
            }
            result.items_processed = len(scanned_files)
            progress.completed = result.items_processed

        except (OSError, ValueError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            progress.failed += 1

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result


class DiffStep(PipelineStep):
    """Diff step — compare two data collections and report differences.

    Expects ``context["source_a"]`` and ``context["source_b"]`` as lists of
    comparable items. Outputs differences into ``context["diff_result"]``.
    """

    def __init__(self, key_fn: str | None = None) -> None:
        super().__init__("diff")
        self.key_fn = key_fn

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        try:
            source_a = context.get("source_a", [])
            source_b = context.get("source_b", [])

            added = [x for x in source_b if x not in source_a]
            removed = [x for x in source_a if x not in source_b]
            common = [x for x in source_a if x in source_b]

            diff_result: dict[str, Any] = {
                "total_a": len(source_a),
                "total_b": len(source_b),
                "added": len(added),
                "removed": len(removed),
                "common": len(common),
                "added_items": added,
                "removed_items": removed,
            }
            context["diff_result"] = diff_result

            result.status = StepStatus.COMPLETED
            result.output = diff_result
            result.items_processed = len(source_a) + len(source_b)
            progress.completed = result.items_processed

        except (TypeError, ValueError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            progress.failed += 1

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result


class ReportStep(PipelineStep):
    """Report step — generate a summary report from all step outputs.

    Collects results from all prior steps via ``context`` and produces a
    structured report in ``context["report"]``.
    """

    def __init__(self) -> None:
        super().__init__("report")

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        try:
            sections: dict[str, Any] = {}

            # Collect scan info
            scanned = context.get("scanned_files", [])
            if scanned:
                sections["scan"] = {"files": len(scanned)}

            # Collect diff info
            diff = context.get("diff_result")
            if diff:
                sections["diff"] = diff

            # Collect validation info
            validation = context.get("validation_result")
            if validation:
                sections["validation"] = validation

            # Collect governance issues
            gov_issues: list[dict] = []
            for key in ("root_namespace_issues", "section_index_issues"):
                issues = context.get(key, [])
                gov_issues.extend(issues)
            if gov_issues:
                sections["governance_issues"] = len(gov_issues)

            report = {
                "summary": sections,
                "total_steps": len(context.get("_executed_steps", [])),
            }
            context["report"] = report

            result.status = StepStatus.COMPLETED
            result.output = report
            result.items_processed = 1
            progress.completed = 1

        except (TypeError, ValueError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            progress.failed += 1

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result
