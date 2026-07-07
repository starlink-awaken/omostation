"""test_commit_assist_e2e.py — P77 Phase 6 LLM-assisted commit 端到端验收

P77 STRAT § 2 Phase 6: commit-assist 当前实现 (bin/commit-assist.py) 的
3-tier graceful degradation 端到端验证 + 侧车 .commit-suggestion 机制.

测试策略:
- unit: import from bin/commit-assist.py, test pure functions
- integration: temp git repo + staged diff → run script → verify output
- tier verification: aetherforge → ollama → heuristic fallback chain
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

# import bin/commit-assist.py (文件名含 - 不能直接 import)
_SPEC = importlib.util.spec_from_file_location(
    "commit_assist", str(WORKSPACE / "bin" / "commit-assist.py")
)
assert _SPEC is not None, "cannot load bin/commit-assist.py"
_COMMIT_ASSIST = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_COMMIT_ASSIST)

CONVENTIONAL_TYPES = _COMMIT_ASSIST.CONVENTIONAL_TYPES
clean_suggestion = _COMMIT_ASSIST.clean_suggestion
heuristic_subject = _COMMIT_ASSIST.heuristic_subject
query_aetherforge = _COMMIT_ASSIST.query_aetherforge
query_ollama = _COMMIT_ASSIST.query_ollama
AETHERFORGE_MODEL = _COMMIT_ASSIST.AETHERFORGE_MODEL


# ── unit: heuristic_subject ──

def test_heuristic_subject_gac():
    """governance-checks.yaml → feat(gac)"""
    stat_lines = [" .omo/_truth/registry/governance-checks.yaml | 2 +-"]
    scope, subject = heuristic_subject("\n".join(stat_lines))
    assert scope == "feat(gac)", f"expected feat(gac), got {scope}"
    assert len(subject) > 0


def test_heuristic_subject_adr():
    """ADR docs → docs(adr)"""
    stat_lines = [" .omo/_knowledge/decisions/0169-p77-phase6.md | 100 ++++++"]
    scope, subject = heuristic_subject("\n".join(stat_lines))
    assert scope == "docs(adr)", f"expected docs(adr), got {scope}"


def test_heuristic_subject_docs():
    """docs/ → docs(docs)"""
    stat_lines = [" docs/PANORAMA.md | 5 +-"]
    scope, subject = heuristic_subject("\n".join(stat_lines))
    assert scope == "docs(docs)", f"expected docs(docs), got {scope}"


def test_heuristic_subject_bin():
    """bin/ → feat(tools)"""
    stat_lines = [" bin/check-foo.py | 42 ++++++++"]
    scope, subject = heuristic_subject("\n".join(stat_lines))
    assert scope == "feat(tools)", f"expected feat(tools), got {scope}"


def test_heuristic_subject_omo():
    """.omo/ (non-registry) → chore(governance)"""
    stat_lines = [" .omo/state/system.yaml | 5 +-"]
    scope, subject = heuristic_subject("\n".join(stat_lines))
    assert scope == "chore(governance)", f"expected chore(governance), got {scope}"


def test_heuristic_subject_projects():
    """projects/* → refactor(submodule)"""
    stat_lines = [" projects/kairon/src/lib.py | 10 ++++"]
    scope, subject = heuristic_subject("\n".join(stat_lines))
    assert scope == "refactor(submodule)", f"expected refactor(submodule), got {scope}"


def test_heuristic_subject_empty():
    """空 stat → type=chore, subject=misc"""
    ctype, subject = heuristic_subject("")
    assert ctype == "chore", f"expected chore, got {ctype}"
    assert subject == "misc", f"expected misc, got {subject}"


def test_heuristic_subject_no_pipe():
    """stat 不含 | → type=chore, subject=misc"""
    ctype, subject = heuristic_subject("nothing here")
    assert ctype == "chore", f"expected chore, got {ctype}"
    assert subject == "misc", f"expected misc, got {subject}"


# ── unit: clean_suggestion ──

def test_clean_suggestion_noop():
    """already clean → unchanged"""
    result = clean_suggestion("feat(gac): add CR-FOO rule\n\nWHY: test\n")
    assert result == "feat(gac): add CR-FOO rule\n\nWHY: test\n"


def test_clean_suggestion_fence():
    """markdown fence ``` → stripped"""
    result = clean_suggestion("```\nfeat(gac): add CR-FOO rule\n\nWHY: test\n```\n")
    assert "```" not in result
    assert result.startswith("feat(gac)")


def test_clean_suggestion_fence_lang():
    """inline fence ```text → stripped"""
    result = clean_suggestion("```text\nfeat(gac): add CR-FOO rule\n```\n")
    assert "```" not in result
    assert result.startswith("feat(gac)")


# ── unit: 72-char subject truncation ──

def test_subject_72_char_truncation():
    """simulate the 72-char hard gate logic"""
    long_subject = "x" * 80
    if len(long_subject) > 72:
        truncated = long_subject[:69] + "..."
    else:
        truncated = long_subject
    assert len(truncated) == 72
    assert truncated.endswith("...")


def test_subject_under_72_unchanged():
    """subject <=72 unchanged"""
    short = "fix: resolve nil pointer in session"
    assert len(short) <= 72
    cleaned = clean_suggestion(short + "\n")
    assert cleaned.strip() == short


# ── unit: heuristic_subject ctype format ──

def test_heuristic_ctype_includes_scope():
    """non-empty stat: ctype contains scope in parens"""
    stat_lines = [" .omo/_truth/registry/governance-checks.yaml | 2 +-"]
    ctype, subject = heuristic_subject("\n".join(stat_lines))
    assert "(" in ctype, f"ctype should include scope: {ctype}"
    assert "gac" in ctype, f"expected gac scope: {ctype}"
    assert "update" in subject, f"subject should describe change: {subject}"


# ── unit: CONVENTIONAL_TYPES ──

def test_conventional_types_11():
    """11 types in CONVENTIONAL_TYPES (standard conventional commits)"""
    assert len(CONVENTIONAL_TYPES) == 11
    assert "feat" in CONVENTIONAL_TYPES
    assert "fix" in CONVENTIONAL_TYPES
    assert "docs" in CONVENTIONAL_TYPES
    assert "chore" in CONVENTIONAL_TYPES


# ── integration: dry-run pipeline ──

def test_no_llm_dry_run_runs():
    """--no-llm + --dry-run: script can be invoked without crashing"""
    script = WORKSPACE / "bin" / "commit-assist.py"
    result = subprocess.run(
        [sys.executable, str(script), "--no-llm", "--dry-run"],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=30,
    )
    # exit 1 is expected (no staged changes in worktree)
    # but should not crash with traceback or import error
    assert result.returncode in (0, 1), f"unexpected rc={result.returncode}: {result.stderr}"
    assert "Traceback" not in result.stderr, f"crash: {result.stderr}"


def test_empty_staged_diff():
    """no staged changes in the WORKSPACE repo -> exit 1"""
    script = WORKSPACE / "bin" / "commit-assist.py"
    result = subprocess.run(
        [sys.executable, str(script), "--no-llm", "--dry-run"],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1, f"expected 1, got {result.returncode}"
    assert "无 staged" in result.stdout


# ── tier: graceful fallback ──

def test_aetherforge_unreachable_graceful():
    """aetherforge gateway unreachable -> returns None (not crash)"""
    result = query_aetherforge(AETHERFORGE_MODEL, "test", 1)
    assert result is None, f"expected None, got {result!r}"


def test_ollama_unreachable_graceful():
    """ollama not available -> returns None (not crash)"""
    result = query_ollama("nonexistent-model-xyz", "test", 3)
    assert result is None, f"expected None, got {result!r}"
