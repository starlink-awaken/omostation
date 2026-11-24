#!/usr/bin/env python3
"""Unit tests for B1.1 retro-field expansion of auto-fix-loop.

Tests:
- New drift kinds FRONTMATTER-MISSING-FIELD, INVALID-METADATA can be
  generated from doc-governance-check output
- apply_fix() recognises the new drift kinds (no crash on dispatch)
- End-to-end script invocation with --json produces valid JSON conforming
  to Drift schema regardless of live repository state
- Hermetic detection of B1.1 kinds and closeout -RETRO-SKIPPED variants
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


class _MonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value):
        old = getattr(target, name)
        setattr(target, name, value)
        self._undo.append(("attr", target, name, old))

    def setenv(self, key, value):
        import os
        old = os.environ.get(key)
        os.environ[key] = value
        self._undo.append(("env", key, old))

    def finish(self):
        import os
        for item in reversed(self._undo):
            if item[0] == "env":
                if item[2] is None:
                    os.environ.pop(item[1], None)
                else:
                    os.environ[item[1]] = item[2]
            elif item[0] == "attr":
                setattr(item[1], item[2], item[3])


def test_apply_fix_handles_new_kinds(monkeypatch=None):
    m = _load()
    mp = monkeypatch if monkeypatch is not None else _MonkeyPatch()
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
    mp.setattr(m.subprocess, "run", _fake_run)

    try:
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
    finally:
        if monkeypatch is None:
            mp.finish()


def test_detect_drifts_generates_b11_and_retro_skipped_kinds(monkeypatch=None):
    """Hermetic unit test: verify detect_drifts generates B1.1 kinds and -RETRO-SKIPPED variants."""
    m = _load()
    mp = monkeypatch if monkeypatch is not None else _MonkeyPatch()

    fake_doc_output = (
        "docs/missing_field.md: missing_frontmatter: missing required frontmatter fields: ['owner']\n"
        "docs/invalid_meta.md: invalid_metadata: status must be one of ['active', 'draft']\n"
        "docs/missing_doc.md: missing_frontmatter: does not start with YAML\n"
        ".omo/_knowledge/retros/retro_missing.md: missing_frontmatter: does not start with YAML\n"
        ".omo/_knowledge/retros/retro_field.md: missing_frontmatter: missing required frontmatter fields: ['owner']\n"
        ".omo/_knowledge/retros/retro_invalid.md: invalid_metadata: status must be one of ['active']\n"
    )

    class _DocResult:
        returncode = 1
        stdout = fake_doc_output
        stderr = ""

    class _EmptyResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        if any("doc-governance-check" in str(c) for c in cmd):
            return _DocResult()
        return _EmptyResult()

    mp.setattr(m.subprocess, "run", _fake_run)
    mp.setattr(m, "_git_diff_ssot", lambda: [])
    mp.setattr(m, "_load_yaml", lambda p: {})

    try:
        # 1. Non-closeout mode: all B1.1 kinds generated directly
        mp.setattr(m, "is_closeout_branch", lambda *args: False)
        drifts = m.detect_drifts()
        kinds = {d.kind for d in drifts}
        assert "FRONTMATTER-MISSING" in kinds
        assert "FRONTMATTER-MISSING-FIELD" in kinds
        assert "INVALID-METADATA" in kinds

        # 2. Closeout mode: retro paths skipped and converted to -RETRO-SKIPPED variants
        mp.setattr(m, "is_closeout_branch", lambda *args: True)
        drifts_closeout = m.detect_drifts()
        kinds_closeout = {d.kind for d in drifts_closeout}
        assert "FRONTMATTER-MISSING-RETRO-SKIPPED" in kinds_closeout
        assert "FRONTMATTER-MISSING-FIELD-RETRO-SKIPPED" in kinds_closeout
        assert "INVALID-METADATA-RETRO-SKIPPED" in kinds_closeout
    finally:
        if monkeypatch is None:
            mp.finish()


def test_json_output_smoke():
    """End-to-end: script --json returns valid JSON conforming to Drift schema."""
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
    assert isinstance(parsed["drifts"], list)
    for d in parsed["drifts"]:
        assert "kind" in d
        assert "severity" in d
        assert "message" in d
        assert "fix_cmd" in d
        assert "auto_fixable" in d


def test_json_output_with_skip_env_var_smoke():
    """End-to-end: SKIP_FIX_LOOP_BRANCH=1 returns valid JSON conforming to schema."""
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
    assert out.returncode in (0, 1), f"unexpected exit: {out.returncode}"
    parsed = json.loads(out.stdout)
    assert "drifts" in parsed
    assert isinstance(parsed["drifts"], list)
    for d in parsed["drifts"]:
        assert "kind" in d
        assert "severity" in d
        assert "message" in d
        assert "fix_cmd" in d
        assert "auto_fixable" in d


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
