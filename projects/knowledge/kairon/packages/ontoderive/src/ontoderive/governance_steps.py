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
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Governance Steps ≡ Module
# 内涵 ≝ {Governance, Steps}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, GovernanceSteps)}
# 功能 ⊢ {Governance_Steps, Init_Governance, Validate_Steps}
# =============================================================================

# ---
# domain: D-Logos
# layer: organ
# status: active
# ---

import re as _re
import time
from pathlib import Path

from .pipeline_models import ProgressInfo, StepResult, StepStatus
from .pipeline_steps.base import PipelineStep

# ============================================================
# Doc Governance: Mechanism 2 — CI Gate Steps
# ============================================================


class RootNamespaceStep(PipelineStep):
    """Gate: no UPPER_CASE.md files at docs/ root (except README.md).

    Flags any file at the top level of ``docs_root`` whose name matches
    ``[A-Z_]{2,}\\.md`` (legacy ALL-CAPS naming) — which is prohibited by
    the SharedBrain naming convention standard.
    """

    # Pattern for legacy UPPER_CASE filenames (2+ chars of A-Z / _)
    _UPPER_PATTERN = _re.compile(r"^[A-Z_]{2,}\.md$")

    def __init__(self, docs_root: Path | None = None) -> None:
        super().__init__("root_namespace")
        self.docs_root = docs_root

    def run(self, docs_root: Path) -> list[dict]:
        """Return a list of issue dicts for each offending file."""
        issues = []
        for md_file in sorted(docs_root.glob("*.md")):
            if md_file.name == "README.md":
                continue
            if self._UPPER_PATTERN.match(md_file.name):
                issues.append(
                    {
                        "rule": "root_namespace",
                        "severity": "medium",
                        "path": str(md_file),
                        "message": (
                            f"UPPER_CASE filename '{md_file.name}' at docs root is prohibited. "
                            "Rename to lowercase kebab-case."
                        ),
                    }
                )
        return issues

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )
        try:
            docs_root = self.docs_root or context.get("docs_root") or context.get("root", Path(".")) / "docs"
            docs_root = Path(docs_root)
            if docs_root.exists():
                issues = self.run(docs_root)
            else:
                issues = []
            result.status = StepStatus.COMPLETED
            result.output = {"issues": issues, "issue_count": len(issues)}
            context["root_namespace_issues"] = issues
        except (OSError, ValueError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result


class SectionIndexStep(PipelineStep):
    """Gate: every docs/{NN}-*/ directory must contain README.md.

    Numbered section directories are structural entry points — they *require*
    an index file so that navigation is never broken.
    """

    _NUMBERED_DIR = _re.compile(r"^\d{2}-")

    def __init__(self, docs_root: Path | None = None) -> None:
        super().__init__("section_index")
        self.docs_root = docs_root

    def run(self, docs_root: Path) -> list[dict]:
        """Return a list of issue dicts for numbered dirs missing README.md."""
        issues = []
        for child in sorted(docs_root.iterdir()):
            if not child.is_dir():
                continue
            if not self._NUMBERED_DIR.match(child.name):
                continue
            readme = child / "README.md"
            if not readme.exists():
                issues.append(
                    {
                        "rule": "section_index",
                        "severity": "medium",
                        "path": str(child),
                        "message": (
                            f"Numbered section directory '{child.name}' is missing README.md. "
                            "Add a README.md index file."
                        ),
                    }
                )
        return issues

    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        start_time = time.time()
        result = StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )
        try:
            docs_root = self.docs_root or context.get("docs_root") or context.get("root", Path(".")) / "docs"
            docs_root = Path(docs_root)
            if docs_root.exists():
                issues = self.run(docs_root)
            else:
                issues = []
            result.status = StepStatus.COMPLETED
            result.output = {"issues": issues, "issue_count": len(issues)}
            context["section_index_issues"] = issues
        except (OSError, ValueError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result


# ============================================================
# Doc Governance: Mechanism 3 — AGENTS.md Context Validation
# ============================================================


class AgentContextStep(PipelineStep):
    """Pipeline step: validate AGENTS.md presence in required directories.

    During the seeding phase issues are reported as warnings so that
    the pipeline does not block while the AGENTS.md network is being
    bootstrapped across the repo.
    """

    def __init__(self, root: Path | None = None) -> None:
        super().__init__("agent_context")
        self.root = root or Path(__file__).parent.parent.parent.parent

    def run(self, root: Path) -> list[dict]:
        """Return issue dicts for required directories that lack AGENTS.md."""
        from .context_compiler import find_missing_contexts

        missing = find_missing_contexts(root)
        issues = []
        for path in missing:
            rel = str(path.relative_to(root))
            issues.append(
                {
                    "rule": "AGENTS_MD_REQUIRED",
                    "severity": "warning",  # warning — seeding phase
                    "path": rel,
                    "message": f"Missing AGENTS.md in required directory: {rel}",
                }
            )
        return issues

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
            issues = self.run(root)
            result.status = StepStatus.COMPLETED
            result.output = {"issues": issues, "issue_count": len(issues)}
            context["agent_context_issues"] = issues
        except (OSError, ValueError) as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
        result.end_time = time.time()
        result.duration = result.end_time - result.start_time
        self._result = result
        return result
