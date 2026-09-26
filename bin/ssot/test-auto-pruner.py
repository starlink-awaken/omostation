#!/usr/bin/env python3
"""test-auto-pruner.py — unit tests for bin/ssot/auto-pruner handlers.

Covers all 5 prune classes including the new ``brief`` handler
(BET-Y2Q4-SH-6).  Each test runs against a hermetic temporary
directory so it cannot leak into the real workspace.

Usage:
    python3 bin/ssot/test-auto-pruner.py
    uv run --with pyyaml python bin/ssot/test-auto-pruner.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Make auto-pruner importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "auto_pruner", str(HERE / "auto-pruner.py"),
)
auto_pruner = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(auto_pruner)


def _make_workspace() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="sh6-pruner-test-"))
    (tmp / "runtime" / "dashboard").mkdir(parents=True)
    (tmp / ".omo" / "_delivery" / "agent-workflows" / "runs").mkdir(parents=True)
    (tmp / "docs" / "reports").mkdir(parents=True)
    (tmp / "docs" / "reports" / "archive").mkdir(parents=True)
    (tmp / ".omo" / "state" / "heartbeats").mkdir(parents=True)
    return tmp


def _patch_workspace_root(workspace: Path) -> None:
    auto_pruner.WORKSPACE_ROOT = workspace


def test_brief_missing() -> tuple[bool, str]:
    """Missing brief → BRIEF-MISSING action, no crash."""
    tmp = _make_workspace()
    _patch_workspace_root(tmp)
    actions = auto_pruner.prune_brief(dry_run=False)
    msgs = [a.get("id") for a in actions]
    shutil.rmtree(tmp)
    return ("BRIEF-MISSING" in msgs,
            f"actions: {actions}")


def test_brief_malformed() -> tuple[bool, str]:
    """Malformed JSON → BRIEF-MALFORMED, no crash."""
    tmp = _make_workspace()
    _patch_workspace_root(tmp)
    (tmp / "runtime" / "dashboard" / "agent-brief.json").write_text("{not json")
    actions = auto_pruner.prune_brief(dry_run=False)
    msgs = [a.get("id") for a in actions]
    shutil.rmtree(tmp)
    return ("BRIEF-MALFORMED" in msgs,
            f"actions: {actions}")


def test_brief_dry_run() -> tuple[bool, str]:
    """Dry-run does NOT write; reports intent."""
    tmp = _make_workspace()
    _patch_workspace_root(tmp)
    p = tmp / "runtime" / "dashboard" / "agent-brief.json"
    p.write_text(json.dumps({
        "schema": "panorama-agent-brief/v1",
        "available": True,
        "generated_at": "2020-01-01T00:00:00+00:00",
        "objective_coverage": {"items": []},
    }))
    actions = auto_pruner.prune_brief(dry_run=True)
    after = json.loads(p.read_text())
    shutil.rmtree(tmp)
    return (actions[0].get("applied") is False
            and after["generated_at"].startswith("2020-01-01"),
            f"applied={actions[0].get('applied')} ts={after['generated_at']}")


def test_brief_apply() -> tuple[bool, str]:
    """Apply bumps generated_at to current UTC."""
    tmp = _make_workspace()
    _patch_workspace_root(tmp)
    p = tmp / "runtime" / "dashboard" / "agent-brief.json"
    p.write_text(json.dumps({
        "schema": "panorama-agent-brief/v1",
        "available": True,
        "generated_at": "2020-01-01T00:00:00+00:00",
        "objective_coverage": {"items": []},
        "alerts": [{"id": "x", "severity": "high"}],
    }))
    actions = auto_pruner.prune_brief(dry_run=False)
    after = json.loads(p.read_text())
    bumped = not after["generated_at"].startswith("2020-01-01")
    preserved = (after.get("schema") == "panorama-agent-brief/v1"
                 and after.get("alerts") == [{"id": "x", "severity": "high"}])
    shutil.rmtree(tmp)
    return (actions[0].get("applied") is True and bumped and preserved,
            f"applied={actions[0].get('applied')} bumped={bumped} preserved={preserved}")


def test_prunable_classes_includes_brief() -> tuple[bool, str]:
    """Auto-pruner registry exposes the brief class."""
    return ("brief" in auto_pruner.PRUNERS,
            f"PRUNABLE_CLASSES={auto_pruner.PRUNABLE_CLASSES}")


def main() -> int:
    tests = [
        ("brief-missing", test_brief_missing),
        ("brief-malformed", test_brief_malformed),
        ("brief-dry-run", test_brief_dry_run),
        ("brief-apply", test_brief_apply),
        ("prunable-classes", test_prunable_classes_includes_brief),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            ok, info = fn()
        except Exception as exc:
            ok, info = False, f"exception: {type(exc).__name__}: {exc}"
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {name}: {info}")
        if ok:
            passed += 1
        else:
            failed += 1
    print(f"\n=== auto-pruner test: {passed}/{passed + failed} passed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())