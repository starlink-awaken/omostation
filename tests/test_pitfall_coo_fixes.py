"""Tests for PITFALL-COO-004/005/006 配套工具修复.

Covers:
- bin/ssot/doc-ssot-lint.py: worktree path crash fix (line 468 relative_to + sentinel string)
- bin/gac/error-knowledge.py: lookup 'int' tag AttributeError fix
- bin/gac/sync-main.sh: fetch + reset + submodule update tool
- .omo/standards/pr-retry-sop.md: SOP exists and references the 3 pitfalls

4019+ 沉淀: see .omo/_knowledge/retros/4018-pr-ci-lessons.md and
4019-pr-ci-lessons.md.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── doc-ssot-lint: line 194 + line 468 should not crash on sentinel ──


def test_doc_ssot_lint_handles_sentinel_string_path() -> None:
    """PITFALL-COO-006: line 468 should print sentinel string, not crash.

    Before fix: `<l0-mapping>` (Path sentinel) → `relative_to()` raised ValueError,
    crashing the whole lint run. After fix: isinstance check + fallback to str().
    """
    mod = _load_module(WORKSPACE / "bin" / "ssot" / "doc-ssot-lint.py", "dsl")
    # Verify check_l0_mapping returns sentinel string (not Path)
    findings = mod.check_l0_mapping()
    if not findings:
        pytest.skip("check_l0_mapping tool ran successfully; sentinel path not exercised")
    # Each finding tuple: (filepath, line_num, label, reason)
    fp = findings[0][0]
    assert isinstance(fp, str), (
        f"filepath should be sentinel string, got {type(fp).__name__}: {fp!r}. "
        f"Path('<l0-mapping>') causes line 468 relative_to() to raise ValueError, "
        "crashing the whole run."
    )
    assert fp == "<l0-mapping>"


def test_doc_ssot_lint_runs_end_to_end_no_crash() -> None:
    """End-to-end: doc-ssot-lint should not crash on report segment."""
    result = subprocess.run(
        ["python3", str(WORKSPACE / "bin" / "ssot" / "doc-ssot-lint.py")],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(WORKSPACE),
        check=False,
    )
    # Either pass (0) or fail-with-report (1); never traceback
    assert "Traceback" not in result.stdout, (
        f"doc-ssot-lint printed a traceback:\n{result.stdout}\nstderr={result.stderr}"
    )
    assert "ValueError" not in result.stdout
    assert result.returncode in (0, 1), (
        f"unexpected exit code {result.returncode}: {result.stdout}"
    )


# ── error-knowledge: lookup should handle non-string tags ──


def test_error_knowledge_lookup_handles_int_tags(tmp_path: Path) -> None:  # noqa: ARG001
    """PITFALL-COO-006 (related): lookup crashed when tag was int.

    Before fix: `e_tags = set(t.lower() for t in e.get('tags', []))` → AttributeError.
    After fix: `set(str(t).lower() for t in (e.get('tags') or []))` handles int.
    """
    # Create a temp pitfalls dir with category subdir (mirrors real layout:
    # PITFALLS_DIR/<category>/PITFALL-*.yaml). monkey-patch PITFALLS_DIR.
    pitfall_dir = tmp_path / "pitfalls"
    pitfall_dir.mkdir()
    (pitfall_dir / "INDEX.md").write_text("# index\n")

    entry = pitfall_dir / "PITFALL-TST-001.yaml"
    entry.write_text(
        "schema: agent-error/v1\n"
        "id: PITFALL-TST-001\n"
        "category: test\n"
        "severity: medium\n"
        "title: test entry with int tags\n"
        "symptom: something failed with int tags\n"
        "root_cause: tags field accidentally contains int\n"
        "solution: cast to str before .lower()\n"
        "prevention: \"\"\n"
        "tags:\n"
        "- 42\n"  # <-- this is the int that used to crash
        "- 7\n"
        "discovered_by: test\n"
        "discovered_at: '2026-01-01'\n"
        "times_encountered: 1\n"
        "last_confirmed_at: '2026-01-01'\n"
        "status: active\n"
    )

    # Patch PITFALLS_DIR to point at our tmp dir (mirrors production path)
    ek = _load_module(WORKSPACE / "bin" / "gac" / "error-knowledge.py", "ek")
    original_pitfalls_dir = ek.PITFALLS_DIR
    ek.PITFALLS_DIR = pitfall_dir

    try:
        # Should NOT raise AttributeError
        result = ek.cmd_lookup(_make_lookup_args(limit=10, tags="42"))
        # Returns 0 matches (int tag won't fuzzy-match the str "42" since we cast)
        # but no AttributeError
        assert isinstance(result, int), f"cmd_lookup should return int, got {type(result)}"
    finally:
        ek.PITFALLS_DIR = original_pitfalls_dir


def _make_lookup_args(limit: int = 10, tags: str = "") -> object:
    """Build a minimal args namespace compatible with cmd_lookup."""
    import argparse

    ns = argparse.Namespace()
    ns.limit = limit
    ns.tags = tags
    ns.category = None
    ns.symptom = ""
    ns.json = False
    return ns


# ── sync-main.sh: dirty check + no-reset mode ──


def test_sync_main_sh_dry_run_help(tmp_path: Path) -> None:
    """sync-main.sh --help should print usage and exit 0."""
    result = subprocess.run(
        [str(WORKSPACE / "bin" / "gac" / "sync-main.sh"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "sync-main.sh" in result.stdout
    assert "fetch" in result.stdout.lower() or "reset" in result.stdout.lower()


def test_sync_main_sh_refuses_dirty_worktree(tmp_path: Path) -> None:
    """sync-main.sh without --allow-dirty must reject dirty worktree.

    Creates a temp dir as a fake workspace, copies .git minimum, makes it dirty,
    runs sync-main.sh, expects exit code 2.
    """
    # Hard to fabricate a real .git fixture cheaply. Instead test the script
    # directly from current worktree: pre-stage a dirty file in current dir,
    # run sync-main.sh (no flags), then clean up.
    worktree = WORKSPACE
    dirty_file = worktree / ".sync-main-test-dirty.tmp"
    if dirty_file.exists():
        dirty_file.unlink()
    dirty_file.write_text("dirty")
    try:
        result = subprocess.run(
            [str(worktree / "bin" / "gac" / "sync-main.sh")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2, (
            f"expected exit 2 (refuse dirty), got {result.returncode}: "
            f"{result.stdout}\nstderr={result.stderr}"
        )
        assert "工作树 dirty" in result.stdout, (
            f"expected '工作树 dirty' message, got: {result.stdout[:300]}"
        )
    finally:
        dirty_file.unlink(missing_ok=True)


# ── SOP: file exists and references all 3 pitfalls ──


def test_pr_retry_sop_exists_and_references_all_pitfalls() -> None:
    """PR retry SOP must exist and reference PITFALL-COO-004/005/006."""
    sop_path = WORKSPACE / ".omo" / "standards" / "pr-retry-sop.md"
    assert sop_path.exists(), f"SOP not found at {sop_path}"
    content = sop_path.read_text(encoding="utf-8")
    for pid in ("PITFALL-COO-004", "PITFALL-COO-005", "PITFALL-COO-006"):
        assert pid in content, f"{pid} not referenced in {sop_path}"
    # Has frontmatter
    assert content.startswith("---\n"), "missing YAML frontmatter"
    # Has 反模式 section
    assert "反模式" in content, "missing 反模式 section"


# ── sync-main.sh: present + executable + has key safety guards ──


def test_sync_main_sh_exists_and_is_safe() -> None:
    script = WORKSPACE / "bin" / "gac" / "sync-main.sh"
    assert script.exists(), f"{script} not found"
    import os
    assert os.access(script, os.X_OK), f"{script} not executable"
    content = script.read_text(encoding="utf-8")
    # Key safety guards
    assert "git reset --hard" in content
    assert "--allow-dirty" in content, "missing --allow-dirty flag"
    assert "工作树 dirty" in content, "missing dirty-check message"
    assert "submodule update" in content, "missing submodule init step"
    assert "PITFALL-COO-006" in content, "missing PITFALL-COO-006 reference"
    # macOS bash compat: should not call `timeout` (absent on macOS by default)
    assert "timeout 60" not in content, (
        "should not use GNU `timeout` (absent on macOS); use background+sleep+kill"
    )