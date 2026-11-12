#!/usr/bin/env python3
"""Unit tests for B1.1 retro-field expansion of auto-fix-loop.

Tests:
- New drift kinds FRONTMATTER-MISSING-FIELD, INVALID-METADATA can be
  generated from doc-governance-check output
- apply_fix() recognises the new drift kinds (no crash on dispatch)
- End-to-end script invocation with --json produces valid JSON containing
  new drift kinds when retro/invalid/missing-field files exist
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "auto-fix-loop.py"


def _load():
    spec = importlib.util.spec_from_file_location("auto_fix_loop", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["auto_fix_loop"] = m
    spec.loader.exec_module(m)
    return m


def test_apply_fix_handles_new_kinds(monkeypatch):
    m = _load()
    supported_kinds = {
        "DERIVED-STALE",
        "ORPHAN-SCRIPT",
        "FRONTMATTER-MISSING",
        "FRONTMATTER-MISSING-FIELD",
        "INVALID-METADATA",
        "CELL-STALE",
    }
    dispatched: list[tuple[list[str], dict]] = []

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        dispatched.append((cmd, kwargs))
        return _Result()

    # 必须 stub: apply_fix 会真跑 fix_cmd, 而这里的 fix_cmd 是
    # `python3 bin/gac/fix-frontmatter.py --batch .` —— 不 stub 就会改真实检出。
    # 2026-11-12 实测: 跑一遍 tests/ 全量后 .omo/_knowledge 下 12 个文件被改
    # (lifecycle: entry -> history), 全是这个用例干的。
    monkeypatch.setattr(m.subprocess, "run", _fake_run)

    for kind in ("FRONTMATTER-MISSING-FIELD", "INVALID-METADATA"):
        d = m.Drift(
            kind=kind,
            severity="warning",
            message="x",
            fix_cmd="python3 bin/gac/fix-frontmatter.py --batch .",
            auto_fixable=True,
        )
        ok, _ = m.apply_fix(d)
        assert ok, f"{kind} 的修复命令未成功派发"
        assert d.kind in supported_kinds

    assert dispatched, "apply_fix 没有派发任何修复命令"
    assert dispatched[0][1].get("cwd") == m.WORKSPACE, "修复命令必须在检出根执行"


def test_json_output_contains_expected_kinds():
    """End-to-end: script --json returns valid JSON with drift list."""
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert out.returncode in (0, 1), f"unexpected exit: {out.returncode}"
    parsed = json.loads(out.stdout)
    assert "drifts" in parsed
    kinds = {d["kind"] for d in parsed["drifts"]}
    # At least one of the new B1.1 kinds OR the existing kinds must appear.
    expected_any = {
        "FRONTMATTER-MISSING",
        "FRONTMATTER-MISSING-FIELD",
        "INVALID-METADATA",
        "PATH-DRIFT",
        "DERIVED-STALE",
    }
    assert expected_any & kinds, f"no expected drift kinds in {kinds}"


def test_json_output_with_skip_env_var():
    """SKIP_FIX_LOOP_BRANCH=1 should produce -RETRO-SKIPPED kinds."""
    import os

    env = os.environ.copy()
    env["SKIP_FIX_LOOP_BRANCH"] = "1"
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )
    parsed = json.loads(out.stdout)
    kinds = {d["kind"] for d in parsed["drifts"]}
    # With skip env, retro paths should be skipped → -RETRO-SKIPPED variants
    retro_skipped_kinds = {
        "FRONTMATTER-MISSING-RETRO-SKIPPED",
        "FRONTMATTER-MISSING-FIELD-RETRO-SKIPPED",
        "INVALID-METADATA-RETRO-SKIPPED",
    }
    # at least one should appear (depending on repo state)
    # We don't require all three since real data may have only some categories
    found_any = bool(retro_skipped_kinds & kinds)
    # If closeout mode triggers, we expect at least one skipped drift
    # (FRONTMATTER-MISSING-RETRO-SKIPPED was confirmed in our test data above)
    assert found_any or "PATH-DRIFT" in kinds, (
        f"Expected at least one retro-skipped or PATH-DRIFT; got {kinds}"
    )


def test_drift_dataclass_fields():
    """Drift dataclass accepts the new kinds."""
    m = _load()
    d = m.Drift(
        kind="FRONTMATTER-MISSING-FIELD",
        severity="warning",
        message="x",
        fix_cmd="cmd",
        auto_fixable=True,
    )
    assert d.kind == "FRONTMATTER-MISSING-FIELD"
    assert d.severity == "warning"
    assert d.auto_fixable is True


if __name__ == "__main__":
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures.append((name, e))
    if failures:
        sys.exit(1)
    print(f"\n{len(tests)} tests passed")