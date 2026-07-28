"""P84 K4 control-experiment harness tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bin" / "collab"))
from control_experiment import compare  # noqa: E402


def test_batch3_runs_and_silent_loss_zero() -> None:
    r = compare("batch3", workers=2)
    assert r["n_paths"] >= 3
    assert r["silent_loss_ok"] is True
    assert r["single"]["n_scenarios"] == r["collab"]["n_scenarios"]


def test_batch4_runs_and_silent_loss_zero() -> None:
    r = compare("batch4", workers=2)
    assert r["n_paths"] >= 1
    assert r["silent_loss_ok"] is True


def test_compare_json_serializable() -> None:
    r = compare("batch4", workers=2)
    json.dumps(r)
