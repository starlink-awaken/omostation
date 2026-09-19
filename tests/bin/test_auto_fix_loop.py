#!/usr/bin/env python3
"""Unit tests for auto-fix-loop.py.

Tests is_closeout_branch and is_retro_path functions.
Run: python3 tests/bin/test_auto_fix_loop.py
"""

from __future__ import annotations

import importlib.util
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


def test_closeout_branch_match_closeout_suffix():
    m = _load()
    assert m.is_closeout_branch("agent/governance-agent/a3-closeout-sop")


def test_closeout_branch_match_a1_through_a9():
    m = _load()
    for n in range(1, 10):
        assert m.is_closeout_branch(f"agent/governance-agent/a{n}-foo")


def test_closeout_branch_match_retro():
    m = _load()
    assert m.is_closeout_branch("agent/governance-agent/t10-125-retro")
    assert m.is_closeout_branch("feat/x-retro")


def test_closeout_branch_match_ledger():
    m = _load()
    assert m.is_closeout_branch("feat/x-ledger-fix")


def test_closeout_branch_match_bet_execution():
    m = _load()
    assert m.is_closeout_branch("bet-execution-2026-09-19")


def test_closeout_branch_no_match_main():
    m = _load()
    assert not m.is_closeout_branch("main")


def test_closeout_branch_no_match_feature():
    m = _load()
    assert not m.is_closeout_branch("feat/some-feature")


def test_closeout_branch_no_match_agent_general():
    m = _load()
    assert not m.is_closeout_branch("agent/governance-agent/fix-bug")
    assert not m.is_closeout_branch("agent/governance-agent/t8-25-panorama")


def test_closeout_branch_no_match_empty():
    m = _load()
    assert not m.is_closeout_branch("")
    assert not m.is_closeout_branch("HEAD")


def test_closeout_branch_env_var_override(monkeypatch):
    m = _load()
    monkeypatch.setenv("SKIP_FIX_LOOP_BRANCH", "1")
    assert m.is_closeout_branch("feat/normal-feature")
    monkeypatch.setenv("SKIP_FIX_LOOP_BRANCH", "true")
    assert m.is_closeout_branch("feat/normal-feature")
    monkeypatch.delenv("SKIP_FIX_LOOP_BRANCH", raising=False)


def test_retro_path_match():
    m = _load()
    assert m.is_retro_path(".omo/_knowledge/retros/A1.md")
    assert m.is_retro_path(".omo/_knowledge/retros/sub/foo.md")
    assert m.is_retro_path(".omo/_knowledge/retrospectives/retros/x.md")


def test_retro_path_no_match():
    m = _load()
    assert not m.is_retro_path("docs/foo.md")
    assert not m.is_retro_path(".omo/_knowledge/audit/x.md")
    assert not m.is_retro_path(".omo/_knowledge/decisions/foo.md")
    assert not m.is_retro_path(".omo/_knowledge/retros.md")  # file at root, not in dir


def test_pattern_constants_present():
    m = _load()
    assert len(m.CLOSEOUT_BRANCH_PATTERNS) >= 4
    assert len(m.RETRO_PATH_PREFIXES) >= 2
    # Default patterns should cover common cases
    assert any("-closeout" in p for p in m.CLOSEOUT_BRANCH_PATTERNS)
    assert any("retros/" in p for p in m.RETRO_PATH_PREFIXES)


if __name__ == "__main__":
    import inspect
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    failures = []
    for name, fn in tests:
        try:
            sig = inspect.signature(fn)
            kwargs = {}
            if "monkeypatch" in sig.parameters:
                import _pytest.monkeypatch as mp_mod
                kwargs["monkeypatch"] = mp_mod.MonkeyPatch()
            fn(**kwargs)
            print(f"  PASS {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures.append((name, e))
    if failures:
        sys.exit(1)
    print(f"\n{len(tests)} tests passed")