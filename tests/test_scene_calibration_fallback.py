"""T7 calibration fallback chain — SSOT agreement + human gate + store proof.

Covers the reconciled contract (SSOT .omo/standards/scene-card-lifecycle.yaml):
- ONE demotion rule: n >= 10 and calibration < 0.5 -> single demote_one_level
  trigger (no <0.6 medium trigger, no fp/trend side-triggers, no demote_to_shadow).
- Proposal-only: check-demotion/daily persist needs_human/* rows to
  scene_lifecycle_log and never touch scene card YAML (no _auto_transition,
  no subprocess in the engine).
- Evaluable record path: record_execution -> compute_calibration populates
  scene_calibration with real execution rows (no fake data).
- Panorama consumption point: verify_chain A/B PASS in this worktree.

DB isolation: the engine's _DB_PATH is redirected to tmp_path; the SSOT and
cruiser sources under test are the real worktree files.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_engine():
    name = "t7_calibration_engine_under_test"
    spec = importlib.util.spec_from_file_location(name, ROOT / "bin/ssot/calibration-engine.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    mod = _load_engine()
    monkeypatch.setattr(mod, "_DB_PATH", tmp_path / "scene-metrics.db")
    return mod


def _seed(mod, scene_id: str, n_ok: int, n_fail: int, confidence: float) -> None:
    for i in range(n_ok):
        mod.record_execution(scene_id, f"run-ok-{i}", {
            "status": "succeeded", "confidence": confidence,
            "duration_ms": 10, "token_usage": 0, "tool_calls": 0,
        })
    for i in range(n_fail):
        mod.record_execution(scene_id, f"run-fail-{i}", {
            "status": "failed", "confidence": confidence,
            "duration_ms": 10, "token_usage": 0, "tool_calls": 0,
        })


def _counts(mod):
    conn = sqlite3.connect(str(mod._DB_PATH))
    cal = conn.execute("SELECT COUNT(*) FROM scene_calibration").fetchone()[0]
    log = conn.execute("SELECT COUNT(*) FROM scene_lifecycle_log").fetchone()[0]
    prop = conn.execute("SELECT COUNT(*) FROM scene_lifecycle_log WHERE reason LIKE 'needs_human/%'").fetchone()[0]
    conn.close()
    return cal, log, prop


# ── evaluable record path ─────────────────────────────────────────────

def test_record_then_compute_populates_calibration(engine) -> None:
    _seed(engine, "t7-test-healthy", n_ok=12, n_fail=0, confidence=0.9)
    cal = engine.compute_calibration("t7-test-healthy")
    assert cal["sample_count"] == 12
    assert cal["calibration_score"] >= 0.5
    cal_n, _, _ = _counts(engine)
    assert cal_n == 1


def test_healthy_scene_does_not_demote(engine) -> None:
    _seed(engine, "t7-test-healthy", n_ok=12, n_fail=0, confidence=0.9)
    demo = engine.check_demotion_triggers("t7-test-healthy")
    assert demo["demote"] is False
    assert demo["triggers"] == []
    _, log_n, _ = _counts(engine)
    assert log_n == 0  # no proposal written without a trigger


# ── ONE demotion rule ─────────────────────────────────────────────────

def test_low_calibration_demotes_one_level_only(engine) -> None:
    _seed(engine, "t7-test-decayed", n_ok=0, n_fail=12, confidence=0.1)
    demo = engine.check_demotion_triggers("t7-test-decayed")
    assert demo["demote"] is True
    assert len(demo["triggers"]) == 1
    assert demo["triggers"][0]["action"] == "demote_one_level"
    assert demo["triggers"][0]["condition"] == "calibration < 0.5"


def test_mid_band_does_not_demote(engine) -> None:
    # score lands in [0.5, 0.6): the rejected <0.6 medium trigger would have
    # fired demote_to_shadow here; the canonical rule must stay silent.
    _seed(engine, "t7-test-mid", n_ok=12, n_fail=18, confidence=0.4)
    cal = engine.compute_calibration("t7-test-mid")
    assert 0.5 <= cal["calibration_score"] < 0.6
    demo = engine.check_demotion_triggers("t7-test-mid", cal=cal)
    assert demo["demote"] is False


def test_below_min_samples_does_not_demote(engine) -> None:
    _seed(engine, "t7-test-few", n_ok=0, n_fail=5, confidence=0.1)
    demo = engine.check_demotion_triggers("t7-test-few")
    assert demo["demote"] is False


# ── human gate: proposals logged, never auto-applied ──────────────────

def test_check_demotion_logs_needs_human_proposal(engine, capsys) -> None:
    _seed(engine, "t7-test-decayed", n_ok=0, n_fail=12, confidence=0.1)
    rc = engine.main(["check-demotion", "--scene-id", "t7-test-decayed"])
    assert rc == 0
    _, log_n, prop_n = _counts(engine)
    assert log_n >= 1
    assert prop_n >= 1
    conn = sqlite3.connect(str(engine._DB_PATH))
    reason = conn.execute("SELECT reason FROM scene_lifecycle_log ORDER BY id DESC LIMIT 1").fetchone()[0]
    actor = conn.execute("SELECT actor FROM scene_lifecycle_log ORDER BY id DESC LIMIT 1").fetchone()[0]
    conn.close()
    assert reason.startswith("needs_human/demote/calibration-drop")
    assert actor == "calibration-engine"
    capsys.readouterr()  # drain CLI output


def test_engine_has_no_auto_transition_surface(engine) -> None:
    assert not hasattr(engine, "_auto_transition")
    assert "subprocess" not in dir(engine)


def test_daily_proposes_without_touching_cards(engine, capsys) -> None:
    _seed(engine, "t7-test-decayed", n_ok=0, n_fail=12, confidence=0.1)
    before = {p.read_text(encoding="utf-8") for p in sorted((ROOT / ".omo/_truth/scenarios/v3").glob("*.yaml"))[:5]}
    rc = engine.main(["daily"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "0 auto-applied (human gate)" in out
    after = {p.read_text(encoding="utf-8") for p in sorted((ROOT / ".omo/_truth/scenarios/v3").glob("*.yaml"))[:5]}
    assert before == after  # no card YAML mutated by the cycle
    _, _, prop_n = _counts(engine)
    assert prop_n >= 1


def test_routine_eligible_still_needs_human(engine) -> None:
    _seed(engine, "t7-test-star", n_ok=100, n_fail=0, confidence=0.95)
    gates = engine.check_promotion_gates("t7-test-star", "routine")
    assert gates["eligible"] is True
    assert gates.get("needs_human") is True


# ── panorama consumption point ────────────────────────────────────────

def test_verify_chain_passes_in_worktree(engine) -> None:
    result = engine.verify_chain(ROOT)
    by_name = {c["name"]: c["status"] for c in result["checks"]}
    assert by_name["threshold-agreement"] == "PASS"
    assert by_name["human-gate"] == "PASS"
    assert result["overall"] == "PASS"
