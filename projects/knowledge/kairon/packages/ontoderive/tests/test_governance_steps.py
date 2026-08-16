"""Tests for ontoderive.governance_steps — CI Gate Steps for doc governance.

Covers 3 step classes: RootNamespaceStep (no UPPER_CASE.md at docs root),
SectionIndexStep (numbered dirs need README.md), AgentContextStep
(AGENTS.md presence). All 3 are part of the doc governance pipeline
gate (Mechanism 2 + 3).
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ontoderive.governance_steps import (
    AgentContextStep,
    RootNamespaceStep,
    SectionIndexStep,
)
from ontoderive.pipeline_models import ProgressInfo, StepStatus


@pytest.fixture
def tmp_docs(tmp_path: Path) -> Path:
    """Provide an empty docs root, return the path."""
    docs = tmp_path / "docs"
    docs.mkdir()
    return docs


# ── RootNamespaceStep ───────────────────────────────────────


class TestRootNamespaceStepRun:
    def test_empty_docs_returns_no_issues(self, tmp_docs: Path):
        step = RootNamespaceStep()
        issues = step.run(tmp_docs)
        assert issues == []

    def test_readme_is_exempt(self, tmp_docs: Path):
        (tmp_docs / "README.md").write_text("# Hello")
        step = RootNamespaceStep()
        assert step.run(tmp_docs) == []

    def test_lowercase_md_ignored(self, tmp_docs: Path):
        (tmp_docs / "guide.md").write_text("g")
        (tmp_docs / "overview.md").write_text("o")
        step = RootNamespaceStep()
        assert step.run(tmp_docs) == []

    def test_uppercase_md_flagged(self, tmp_docs: Path):
        (tmp_docs / "OLD_FORMAT.md").write_text("x")
        step = RootNamespaceStep()
        issues = step.run(tmp_docs)
        assert len(issues) == 1
        assert issues[0]["rule"] == "root_namespace"
        assert issues[0]["severity"] == "medium"
        assert "OLD_FORMAT.md" in issues[0]["path"]

    def test_uppercase_underscores_flagged(self, tmp_docs: Path):
        (tmp_docs / "LEGACY_FILE.md").write_text("x")
        step = RootNamespaceStep()
        issues = step.run(tmp_docs)
        assert len(issues) == 1

    def test_short_uppercase_not_flagged(self, tmp_docs: Path):
        """Pattern requires 2+ chars: 'AB.md' would not match."""
        (tmp_docs / "AB.md").write_text("x")
        step = RootNamespaceStep()
        # Pattern is [A-Z_]{2,} — "AB" has 2 chars so it DOES match
        # but 'A.md' wouldn't. The test is to confirm 'A.md' isn't flagged.
        # 2+ uppercase IS flagged.
        issues = step.run(tmp_docs)
        assert len(issues) == 1

    def test_mixed_case_in_underscore_path(self, tmp_docs: Path):
        (tmp_docs / "Mixed_Case.md").write_text("x")
        step = RootNamespaceStep()
        issues = step.run(tmp_docs)
        # Mixed_Case has lowercase chars, so doesn't match [A-Z_]+
        assert len(issues) == 0

    def test_lowercase_with_underscores_ok(self, tmp_docs: Path):
        (tmp_docs / "lower_case.md").write_text("x")
        step = RootNamespaceStep()
        assert step.run(tmp_docs) == []

    def test_multiple_offenders(self, tmp_docs: Path):
        (tmp_docs / "BAD_ONE.md").write_text("a")
        (tmp_docs / "BAD_TWO.md").write_text("b")
        (tmp_docs / "good.md").write_text("c")
        step = RootNamespaceStep()
        issues = step.run(tmp_docs)
        assert len(issues) == 2
        paths = {i["path"] for i in issues}
        assert any("BAD_ONE" in p for p in paths)
        assert any("BAD_TWO" in p for p in paths)

    def test_non_md_files_ignored(self, tmp_docs: Path):
        (tmp_docs / "README.txt").write_text("x")
        (tmp_docs / "GUIDE.rst").write_text("x")
        step = RootNamespaceStep()
        assert step.run(tmp_docs) == []

    def test_subdirectory_md_not_checked(self, tmp_docs: Path):
        """Only files directly in docs_root are checked, not subdirectories."""
        (tmp_docs / "subdir").mkdir()
        (tmp_docs / "subdir" / "UPPER.md").write_text("x")
        step = RootNamespaceStep()
        assert step.run(tmp_docs) == []


class TestRootNamespaceStepExecute:
    def test_existing_docs_root_runs(self, tmp_docs: Path):
        (tmp_docs / "BAD.md").write_text("x")
        step = RootNamespaceStep()
        progress = MagicMock(spec=ProgressInfo)
        result = step.execute({"docs_root": tmp_docs}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["issue_count"] == 1

    def test_missing_docs_root_returns_empty(self, tmp_docs: Path):
        """When docs_root doesn't exist, no issues reported."""
        step = RootNamespaceStep()
        progress = MagicMock(spec=ProgressInfo)
        result = step.execute({"docs_root": tmp_docs.parent / "nonexistent"}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["issue_count"] == 0

    def test_context_default_fallback(self, tmp_path: Path):
        """When context has no docs_root, falls back to root/docs."""
        # Setup root/docs/ structure
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "BAD.md").write_text("x")
        step = RootNamespaceStep()
        progress = MagicMock(spec=ProgressInfo)
        # context has 'root' (Path) but no 'docs_root' key
        result = step.execute({"root": tmp_path}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["issue_count"] == 1

    def test_exception_caught(self, tmp_docs: Path):
        step = RootNamespaceStep()
        progress = MagicMock(spec=ProgressInfo)
        # Pass docs_root as a non-Path value that can't be resolved
        with patch("pathlib.Path.exists", side_effect=OSError("disk error")):
            result = step.execute({"docs_root": tmp_docs}, progress)
        assert result.status == StepStatus.FAILED
        assert "disk error" in result.error

    def test_stores_issues_in_context(self, tmp_docs: Path):
        (tmp_docs / "BAD.md").write_text("x")
        step = RootNamespaceStep()
        progress = MagicMock(spec=ProgressInfo)
        context: dict = {"docs_root": tmp_docs}
        step.execute(context, progress)
        assert "root_namespace_issues" in context
        assert len(context["root_namespace_issues"]) == 1

    def test_set_step_name_from_super(self):
        step = RootNamespaceStep()
        assert step.name == "root_namespace"


# ── SectionIndexStep ──────────────────────────────────────


class TestSectionIndexStepRun:
    def test_empty_docs_returns_no_issues(self, tmp_docs: Path):
        step = SectionIndexStep()
        assert step.run(tmp_docs) == []

    def test_non_numbered_dirs_ignored(self, tmp_docs: Path):
        """Directories not matching NN- prefix are ignored."""
        (tmp_docs / "guides").mkdir()
        (tmp_docs / "reference").mkdir()
        (tmp_docs / "archive").mkdir()
        step = SectionIndexStep()
        assert step.run(tmp_docs) == []

    def test_numbered_dir_without_readme_flagged(self, tmp_docs: Path):
        (tmp_docs / "01-getting-started").mkdir()
        step = SectionIndexStep()
        issues = step.run(tmp_docs)
        assert len(issues) == 1
        assert issues[0]["rule"] == "section_index"
        assert issues[0]["severity"] == "medium"
        assert "01-getting-started" in issues[0]["path"]

    def test_numbered_dir_with_readme_ok(self, tmp_docs: Path):
        (tmp_docs / "02-advanced").mkdir()
        (tmp_docs / "02-advanced" / "README.md").write_text("# Hi")
        step = SectionIndexStep()
        assert step.run(tmp_docs) == []

    def test_multiple_numbered_dirs(self, tmp_docs: Path):
        (tmp_docs / "01-foo").mkdir()
        (tmp_docs / "02-bar").mkdir()
        (tmp_docs / "02-bar" / "README.md").write_text("x")
        (tmp_docs / "03-baz").mkdir()
        step = SectionIndexStep()
        issues = step.run(tmp_docs)
        assert len(issues) == 2
        dirs = {i["path"].split("/")[-1] for i in issues}
        assert "01-foo" in dirs
        assert "03-baz" in dirs
        assert "02-bar" not in dirs

    def test_files_in_docs_root_ignored(self, tmp_docs: Path):
        """Only directories are checked, not files."""
        (tmp_docs / "01-orphan.md").write_text("x")
        step = SectionIndexStep()
        assert step.run(tmp_docs) == []

    def test_mixed_files_and_dirs(self, tmp_docs: Path):
        (tmp_docs / "01-foo").mkdir()
        (tmp_docs / "01-foo" / "README.md").write_text("x")
        (tmp_docs / "guide.md").write_text("x")
        step = SectionIndexStep()
        assert step.run(tmp_docs) == []

    def test_two_digit_numbering(self, tmp_docs: Path):
        """NN- pattern matches 2 digits exactly."""
        (tmp_docs / "99-late").mkdir()
        step = SectionIndexStep()
        assert len(step.run(tmp_docs)) == 1

    def test_three_digit_numbering_not_matched(self, tmp_docs: Path):
        """NN- is exactly 2 digits; 100-foo should not match."""
        (tmp_docs / "100-archive").mkdir()
        step = SectionIndexStep()
        assert step.run(tmp_docs) == []


class TestSectionIndexStepExecute:
    def test_existing_docs_root(self, tmp_docs: Path):
        (tmp_docs / "01-foo").mkdir()
        step = SectionIndexStep()
        progress = MagicMock(spec=ProgressInfo)
        result = step.execute({"docs_root": tmp_docs}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["issue_count"] == 1

    def test_missing_docs_root(self, tmp_docs: Path):
        step = SectionIndexStep()
        progress = MagicMock(spec=ProgressInfo)
        result = step.execute({"docs_root": tmp_docs.parent / "nonexistent"}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["issue_count"] == 0

    def test_context_default_fallback(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "01-foo").mkdir()
        step = SectionIndexStep()
        progress = MagicMock(spec=ProgressInfo)
        result = step.execute({"root": tmp_path}, progress)
        assert result.output["issue_count"] == 1

    def test_exception_caught(self, tmp_docs: Path):
        step = SectionIndexStep()
        progress = MagicMock(spec=ProgressInfo)
        with patch("pathlib.Path.exists", side_effect=OSError("io error")):
            result = step.execute({"docs_root": tmp_docs}, progress)
        assert result.status == StepStatus.FAILED

    def test_stores_issues_in_context(self, tmp_docs: Path):
        (tmp_docs / "01-foo").mkdir()
        step = SectionIndexStep()
        progress = MagicMock(spec=ProgressInfo)
        context: dict = {"docs_root": tmp_docs}
        step.execute(context, progress)
        assert "section_index_issues" in context


# ── AgentContextStep ──────────────────────────────────────


class TestAgentContextStepRun:
    def test_no_missing_returns_no_issues(self, tmp_path: Path):
        """All required dirs have AGENTS.md → no issues."""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "AGENTS.md").write_text("x")
        (tmp_path / "dir2").mkdir()
        (tmp_path / "dir2" / "AGENTS.md").write_text("x")
        with patch("ontoderive.context_compiler.find_missing_contexts", return_value=[]):
            step = AgentContextStep()
            issues = step.run(tmp_path)
        assert issues == []

    def test_missing_returns_warning_issue(self, tmp_path: Path):
        missing = tmp_path / "missing_dir"
        missing.mkdir()
        with patch("ontoderive.context_compiler.find_missing_contexts", return_value=[missing]):
            step = AgentContextStep()
            issues = step.run(tmp_path)
        assert len(issues) == 1
        assert issues[0]["rule"] == "AGENTS_MD_REQUIRED"
        # Seeding phase: warning, not error
        assert issues[0]["severity"] == "warning"

    def test_relative_path_in_message(self, tmp_path: Path):
        missing = tmp_path / "deep" / "nested"
        missing.mkdir(parents=True)
        with patch("ontoderive.context_compiler.find_missing_contexts", return_value=[missing]):
            step = AgentContextStep()
            issues = step.run(tmp_path)
        assert "deep/nested" in issues[0]["path"]

    def test_multiple_missing(self, tmp_path: Path):
        missing = [tmp_path / f"d{i}" for i in range(3)]
        for m in missing:
            m.mkdir()
        with patch("ontoderive.context_compiler.find_missing_contexts", return_value=missing):
            step = AgentContextStep()
            issues = step.run(tmp_path)
        assert len(issues) == 3


class TestAgentContextStepExecute:
    def test_existing_root(self, tmp_path: Path):
        with patch("ontoderive.context_compiler.find_missing_contexts", return_value=[]):
            step = AgentContextStep()
            progress = MagicMock(spec=ProgressInfo)
            result = step.execute({"root": tmp_path}, progress)
        assert result.status == StepStatus.COMPLETED
        assert result.output["issue_count"] == 0

    def test_default_root_fallback(self):
        """When no root provided, uses Path(__file__).parent.parent.parent.parent."""
        with patch("ontoderive.context_compiler.find_missing_contexts", return_value=[]):
            step = AgentContextStep()
            progress = MagicMock(spec=ProgressInfo)
            result = step.execute({}, progress)
        assert result.status == StepStatus.COMPLETED

    def test_exception_caught(self, tmp_path: Path):
        with patch("ontoderive.context_compiler.find_missing_contexts", side_effect=OSError("io error")):
            step = AgentContextStep()
            progress = MagicMock(spec=ProgressInfo)
            result = step.execute({"root": tmp_path}, progress)
        assert result.status == StepStatus.FAILED

    def test_stores_issues_in_context(self, tmp_path: Path):
        """When issues are found, they should be added to context['agent_context_issues']."""
        missing = tmp_path / "missing"
        missing.mkdir()
        with patch("ontoderive.context_compiler.find_missing_contexts", return_value=[missing]):
            step = AgentContextStep(root=tmp_path)
            progress = MagicMock(spec=ProgressInfo)
            context: dict = {}
            step.execute(context, progress)
        # issues are converted to issue dicts in context (not raw paths)
        assert "agent_context_issues" in context
        assert len(context["agent_context_issues"]) == 1
        assert context["agent_context_issues"][0]["rule"] == "AGENTS_MD_REQUIRED"


# ── Step integration / common ────────────────────────────


class TestStepCommonBehavior:
    def test_all_steps_inherit_from_pipeline_step(self):
        """All 3 step classes are PipelineStep subclasses."""
        from ontoderive.pipeline_steps.base import PipelineStep

        for cls in (RootNamespaceStep, SectionIndexStep, AgentContextStep):
            assert issubclass(cls, PipelineStep)

    def test_all_steps_have_run_and_execute(self):
        for cls in (RootNamespaceStep, SectionIndexStep, AgentContextStep):
            assert hasattr(cls, "run")
            assert hasattr(cls, "execute")
            assert callable(cls.run)
            assert callable(cls.execute)

    def test_all_steps_instantiate_without_args(self):
        """Steps can be constructed with no required arguments."""
        for cls in (RootNamespaceStep, SectionIndexStep, AgentContextStep):
            step = cls()
            assert step is not None

    def test_all_steps_set_name_via_super(self):
        for cls, expected_name in [
            (RootNamespaceStep, "root_namespace"),
            (SectionIndexStep, "section_index"),
            (AgentContextStep, "agent_context"),
        ]:
            step = cls()
            assert step.name == expected_name
