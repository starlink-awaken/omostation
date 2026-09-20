#!/usr/bin/env python3
"""Unit tests for claim-suggester.py.

Tests run_git_log, detect_* functions, and dedup against existing BET IDs.
Run: python3 tests/bin/test_claim_suggester.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "claim-suggester.py"


def _load():
    spec = importlib.util.spec_from_file_location("claim_suggester", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["claim_suggester"] = m
    spec.loader.exec_module(m)
    return m


def test_run_git_log_returns_list():
    m = _load()
    result = m.run_git_log(30)
    assert isinstance(result, list)
    for line in result:
        assert "|" in line, f"Unexpected format: {line!r}"


def test_detect_consolidation_basic():
    m = _load()
    commits = [
        "abc1234|fix(panorama): A",
        "def5678|fix(panorama): B",
        "999aa11|fix(panorama): C",
        "bbbccdd|fix(scope): D",
    ]
    out = m.detect_consolidation(commits, 30)
    panorama = [s for s in out if s["scope"] == "panorama"]
    assert len(panorama) == 1
    assert panorama[0]["fix_count"] == 3
    assert panorama[0]["kind"] == "CONSOLIDATION"


def test_detect_consolidation_threshold():
    m = _load()
    commits = ["abc1234|fix(small): X", "def5678|fix(small): Y"]
    out = m.detect_consolidation(commits, 30)
    small = [s for s in out if s["scope"] == "small"]
    assert len(small) == 0


def test_detect_track_deepening_panorama():
    m = _load()
    commits = [
        "abc1234|feat(panorama): X0",
        "def5678|feat(panorama): X1",
        "999aa11|feat(panorama): X2",
        "bbbccdd|feat(panorama): X3",
        "1112223|feat(panorama): X4",
    ]
    out = m.detect_track_deepening(commits)
    tracks = {s["track"] for s in out}
    assert "panorama" in tracks


def test_detect_track_deepening_threshold():
    m = _load()
    commits = [
        "abc1234|feat(panorama): X",
        "def5678|feat(panorama): Y",
    ]
    out = m.detect_track_deepening(commits)
    panorama = [s for s in out if s["track"] == "panorama"]
    assert len(panorama) == 0


def test_detect_orphan_wip():
    m = _load()
    commits = [
        "abc1234|fix(normal): real commit",
        "def5678|WIP on agent/governance-agent/foo: 1234567",
    ]
    out = m.detect_orphan_wip(commits)
    assert len(out) == 1
    assert out[0]["kind"] == "ORPHAN-WIP"
    assert out[0]["wip_sha"] == "def5678"


def test_detect_orphan_wip_none():
    m = _load()
    commits = ["abc1234|fix(x): y", "def5678|feat(z): w"]
    out = m.detect_orphan_wip(commits)
    assert len(out) == 0


def test_detect_doc_drift():
    m = _load()
    commits = [f"{a:02x}1234|chore(tasks): X{a}" for a in range(6)]
    out = m.detect_doc_drift(commits)
    assert len(out) == 1
    assert out[0]["kind"] == "DOC-DRIFT"


def test_detect_doc_drift_below_threshold():
    m = _load()
    commits = [
        "ab1234|chore(tasks): X",
        "cd5678|chore(tasks): Y",
    ]
    out = m.detect_doc_drift(commits)
    assert len(out) == 0


def test_get_existing_bet_ids_returns_set():
    m = _load()
    ids = m.get_existing_bet_ids()
    assert isinstance(ids, set)
    assert len(ids) > 100


if __name__ == "__main__":
    import inspect
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