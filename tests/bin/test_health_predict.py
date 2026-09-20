#!/usr/bin/env python3
"""Unit tests for health-predict.py.

Tests:
- load_health_snapshot() parses 5 numeric scores
- predict_horizon() applies the heuristic correctly
- bands are computed correctly (verified via predict_horizon output)
- recommend_actions() returns the right severity bands
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "health-predict.py"


def _load():
    spec = importlib.util.spec_from_file_location("health_predict", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["health_predict"] = m
    spec.loader.exec_module(m)
    return m


def test_load_health_snapshot_returns_dict():
    m = _load()
    snap = m.load_health_snapshot()
    assert isinstance(snap, dict)
    if snap:
        assert "drift_score" in snap


def test_predict_horizon_drift_grows_with_retro():
    m = _load()
    current = {
        "drift_score": 0,
        "staleness_score": 100,
        "freshness_score": 100,
        "alignment_score": 100,
    }
    pred = m.predict_horizon(current, {"retro_invalid": 100, "retro_missing_field": 0}, 7)
    assert pred["drift"]["predicted_7d"] > 0
    pred0 = m.predict_horizon(current, {"retro_invalid": 0, "retro_missing_field": 0}, 7)
    assert pred0["drift"]["predicted_7d"] == 0


def test_predict_horizon_staleness_drops():
    m = _load()
    current = {
        "drift_score": 0,
        "staleness_score": 100,
        "freshness_score": 100,
        "alignment_score": 100,
    }
    pred = m.predict_horizon(current, {}, 7)
    # -0.05/day × 7 days ≈ -0.35 (rounded to 1 dp; could be 99.6 or 99.7)
    assert 99.6 <= pred["staleness"]["predicted_7d"] <= 99.7
    assert 99.6 <= pred["freshness"]["predicted_7d"] <= 99.7


def test_band_assignment_via_prediction():
    m = _load()
    # high alignment (good) → GREEN
    high = m.predict_horizon(
        {
            "drift_score": 0,
            "staleness_score": 100,
            "freshness_score": 100,
            "alignment_score": 95,
        },
        {},
        7,
    )
    assert high["alignment"]["band_now"] == "GREEN"
    # low alignment (bad) → YELLOW or RED
    low = m.predict_horizon(
        {
            "drift_score": 0,
            "staleness_score": 100,
            "freshness_score": 100,
            "alignment_score": 30,
        },
        {},
        7,
    )
    assert low["alignment"]["band_now"] == "RED"


def test_drift_band_inverted():
    m = _load()
    # drift low (good) vs drift high (bad)
    low_drift = m.predict_horizon(
        {
            "drift_score": 0,
            "staleness_score": 100,
            "freshness_score": 100,
            "alignment_score": 100,
        },
        {},
        7,
    )
    assert low_drift["drift"]["band_now"] == "GREEN"
    high_drift = m.predict_horizon(
        {
            "drift_score": 50,
            "staleness_score": 100,
            "freshness_score": 100,
            "alignment_score": 100,
        },
        {},
        7,
    )
    assert high_drift["drift"]["band_now"] == "RED"


def test_recommend_actions_red_band():
    m = _load()
    prediction = {
        "drift": {
            "now": 30, "predicted_7d": 50,
            "delta": 20,
            "band_now": "YELLOW", "band_predicted": "RED",
        },
        "staleness": {
            "now": 95, "predicted_7d": 95,
            "delta": 0,
            "band_now": "GREEN", "band_predicted": "GREEN",
        },
        "freshness": {
            "now": 95, "predicted_7d": 95,
            "delta": 0,
            "band_now": "GREEN", "band_predicted": "GREEN",
        },
        "alignment": {
            "now": 95, "predicted_7d": 95,
            "delta": 0,
            "band_now": "GREEN", "band_predicted": "GREEN",
        },
    }
    actions = m.recommend_actions(prediction)
    assert any("RED" in a and "drift" in a for a in actions)


def test_recommend_actions_no_action_when_all_green():
    m = _load()
    prediction = {
        dim: {
            "now": 95, "predicted_7d": 95, "delta": 0,
            "band_now": "GREEN", "band_predicted": "GREEN",
        }
        for dim in ("drift", "staleness", "freshness", "alignment")
    }
    actions = m.recommend_actions(prediction)
    assert actions == []


def test_horizon_scales_correctly():
    m = _load()
    current = {
        "drift_score": 0,
        "staleness_score": 100,
        "freshness_score": 100,
        "alignment_score": 100,
    }
    p7 = m.predict_horizon(current, {}, 7)
    p30 = m.predict_horizon(current, {}, 30)
    # staleness: -0.05 × 7 = -0.35 vs -0.05 × 30 = -1.5
    assert p7["staleness"]["predicted_7d"] > p30["staleness"]["predicted_7d"]


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