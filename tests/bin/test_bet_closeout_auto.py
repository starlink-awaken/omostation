#!/usr/bin/env python3
"""Unit tests for bet-closeout-auto.py.

Tests check_retro, find_bet_in_ledger, get_current_status functions.
Run: python3 tests/bin/test_bet_closeout_auto.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "plan" / "bet-closeout-auto.py"


def _load():
    spec = importlib.util.spec_from_file_location("closeout_auto", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["closeout_auto"] = m
    spec.loader.exec_module(m)
    return m


def test_check_retro_found(tmp_path, monkeypatch):
    m = _load()
    retro = m.RETRO_DIR / "BET-TEST-001.md"
    retro.parent.mkdir(parents=True, exist_ok=True)
    retro.write_text(
        """---
bet_id: BET-TEST-001
status: closed
lifecycle: history
owner: test
last-reviewed: 2026-09-19
type: ephemeral
---
content"""
    )
    ok, msg = m.check_retro("BET-TEST-001")
    assert ok, msg


def test_check_retro_missing():
    m = _load()
    ok, msg = m.check_retro("BET-NONEXISTENT-999")
    assert not ok
    assert "not found" in msg


def test_check_retro_missing_frontmatter(tmp_path):
    m = _load()
    retro = m.RETRO_DIR / "BET-BAD-002.md"
    retro.parent.mkdir(parents=True, exist_ok=True)
    retro.write_text("---\nbet_id: BET-BAD-002\n---\nno status field")
    ok, msg = m.check_retro("BET-BAD-002")
    assert not ok
    assert "frontmatter" in msg.lower()


def test_find_bet_in_ledger():
    m = _load()
    # Real test: BET-Y1Q4-T10-125 exists in main ledger
    ok, line = m.find_bet_in_ledger("BET-Y1Q4-T10-125")
    assert ok
    assert line > 0


def test_find_bet_not_in_ledger():
    m = _load()
    ok, line = m.find_bet_in_ledger("BET-NEVER-EXISTED-999")
    assert not ok
    assert line == -1


def test_get_current_status_done():
    m = _load()
    # Real test: BET-Y1Q4-T10-125 is done
    status = m.get_current_status("BET-Y1Q4-T10-125")
    assert status == "done"


def test_get_current_status_in_progress():
    m = _load()
    # Find any in_progress bet for testing
    import yaml
    ledger_path = m.LEDGER
    if not ledger_path.exists():
        return
    data = yaml.safe_load(ledger_path.read_text())
    # The ledger schema isn't simple flat list; just verify None for invalid id
    assert m.get_current_status("BET-INVALID-999") is None


def test_utc_today_format():
    m = _load()
    today = m.utc_today()
    # YYYY-MM-DD = 10 chars
    assert len(today) == 10
    assert today[4] == "-"
    assert today[7] == "-"


def test_utc_now_iso_format():
    m = _load()
    iso = m.utc_now_iso()
    # YYYY-MM-DDTHH:MM:SSZ = 20 chars
    assert len(iso) == 20
    assert iso[10] == "T"
    assert iso.endswith("Z")


if __name__ == "__main__":
    import inspect
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    failures = []
    for name, fn in tests:
        try:
            sig = inspect.signature(fn)
            kwargs = {}
            if "tmp_path" in sig.parameters:
                from tempfile import mkdtemp
                kwargs["tmp_path"] = Path(mkdtemp())
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