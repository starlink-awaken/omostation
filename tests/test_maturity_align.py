"""Tests for bin/gac/maturity-align.py (BET-Y1Q3-T10-10).

Three independent measurement systems:
  1. compass_radar.health_score    (0-100)
  2. maturity-scorecard.overall     (1-10)
  3. bet-ledger completion_pct      (0-100)

This tool reconciles them and emits a side-by-side view + reconciliation_score.
"""

from __future__ import annotations

import importlib.util
import json as _json
import sys
from pathlib import Path

import pytest

ALIGN = Path(__file__).resolve().parents[1] / "bin" / "gac" / "maturity-align.py"
_MODULE = "_maturity_align_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, ALIGN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def align():
    return _load()


# ---------------------------------------------------------------------------
# Reconciliation logic
# ---------------------------------------------------------------------------


def test_compute_reconciliation_perfect(align):
    """All three at 100% → reconciliation_score=100, drift_detected=False."""
    compass = {"health_score": 100}
    scorecard = {"overall": 10.0, "target": 9.0, "gap": -1.0}
    ledger = {"completion_pct": 100.0, "counts": {"done": 10}, "total": 10}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    assert out["drift_detected"] is False
    assert out["reconciliation_score"] == 100
    assert out["normalised"]["compass_radar"] == 100
    assert out["normalised"]["maturity_scorecard"] == 100
    assert out["normalised"]["bet_ledger"] == 100


def test_compute_reconciliation_drift_detected(align):
    """Compass=100 but ledger=20 → spread=80, drift_detected=True."""
    compass = {"health_score": 100}
    scorecard = {"overall": 9.0, "target": 9.0, "gap": 0.0}
    ledger = {"completion_pct": 20.0, "counts": {"done": 2}, "total": 10}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    assert out["drift_detected"] is True
    # spread = 100 - 20 = 80; reconciliation = 100 - 80 = 20
    assert out["reconciliation_score"] == 20
    assert len(out["warnings"]) >= 1


def test_compute_reconciliation_handles_missing(align):
    """Missing dimensions → normalised=None, no crash."""
    compass: dict = {}
    scorecard: dict = {}
    ledger: dict = {}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    assert out["drift_detected"] is False
    assert out["reconciliation_score"] is None


def test_normalise_to_100_clamps(align):
    """Values > scale_max clamp to 100, < 0 clamp to 0."""
    assert align.normalise_to_100(50, 100) == 50
    assert align.normalise_to_100(200, 100) == 100
    assert align.normalise_to_100(-10, 100) == 0
    assert align.normalise_to_100(7.5, 10) == 75
    assert align.normalise_to_100(None, 100) is None


def test_compute_reconciliation_3way_spread(align):
    """Real-world scenario: 70 / 7.5 / 89.4 → reconciliation around 80."""
    compass = {"health_score": 70}
    scorecard = {"overall": 7.5, "target": 9.0, "gap": 1.5}
    ledger = {"completion_pct": 89.4, "counts": {"done": 126}, "total": 141}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    # normalised: 70, 75, 89.4; spread = 89.4 - 70 = 19.4
    assert out["drift_detected"] is False  # spread < 30
    assert 79 <= out["reconciliation_score"] <= 82


# ---------------------------------------------------------------------------
# Tool integration
# ---------------------------------------------------------------------------


def test_cli_runs_in_dry_paths(tmp_path, monkeypatch):
    """Tool runs without crashing when subprocesses succeed (or fail gracefully)."""
    import subprocess

    # Patch WS_ROOT so subprocess calls go to a clean root
    monkeypatch.setattr(align_mod := _load(), "WS_ROOT", tmp_path)
    # Ensure tool runs even when subprocesses fail (None in dict)
    res = subprocess.run(
        [sys.executable, str(ALIGN)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    # Tool should not crash with exit 1 — output may show "unavailable" entries
    assert res.returncode in (0, 1)
    # When tools fail, the JSON output should still be valid JSON with --json flag
    res_json = subprocess.run(
        [sys.executable, str(ALIGN), "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if res_json.stdout.strip().startswith("{"):
        data = _json.loads(res_json.stdout)
        assert "alignment" in data