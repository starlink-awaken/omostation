"""Tests for compass_radar T10-05 integration of drift-sweep + kb-staleness.

The T10-05 BET added two new dimensions to the composite health score:
- drift_score: parsed from `bin/gac/drift-sweep.py --json` summary block
- staleness_score: parsed from `bin/kb/staleness-check.py --json` counts

These tests:
1. Verify the collectors gracefully degrade when subprocess fails (return None)
2. Verify the composite formula integrates the new dimensions
3. Verify backward compat: old 4-arg call still produces same weights
"""

from __future__ import annotations

import importlib.util
import json as _json
import sys
from pathlib import Path

import pytest

RADAR = Path(__file__).resolve().parents[1] / "bin" / "compass_radar.py"
_MODULE = "_compass_radar_t1005_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, RADAR)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def radar():
    return _load()


# ---------------------------------------------------------------------------
# Composite score: new dimensions
# ---------------------------------------------------------------------------


def test_composite_legacy_4arg_signature_unchanged(radar):
    """Old 4-arg call (gov, ratio, fresh, fb) keeps baseline weights.

    regression guard: T10-05 added drift/staleness as keyword-only optional
    args; passing them as None must yield the same weights as before.
    """
    score, bd = radar._composite_health_score(
        100,  # governance
        1.0,  # service_online_ratio
        100,  # freshness
        True,  # feedback_alive
    )
    assert bd["weights"]["governance"] == 0.3
    assert bd["weights"]["runtime"] == 0.5
    assert bd["weights"]["freshness"] == 0.2
    assert "drift" not in bd["weights"]
    assert "staleness" not in bd["weights"]
    assert score == 100  # all perfect


def test_composite_with_drift_and_staleness(radar):
    """New dimensions lower composite when drift/staleness are imperfect.

    Perfect governance/runtime/freshness but drift=50, staleness=50 should
    give:
      contributions: gov=30, runtime=50, fresh=20, drift=5, staleness=5 → 110
      total_weight = 1.20 → raw = 110/1.20 ≈ 91.67 → 92
    """
    score, bd = radar._composite_health_score(
        100,
        1.0,
        100,
        True,
        drift_score=50,
        staleness_score=50,
    )
    assert bd["weights"]["drift"] == 0.10
    assert bd["weights"]["staleness"] == 0.10
    assert bd["contributions"]["drift"] == 50 * 0.10
    assert bd["contributions"]["staleness"] == 50 * 0.10
    assert score == 92


def test_composite_partial_drift_only(radar):
    """Only drift available, staleness missing → still integrate drift."""
    score, bd = radar._composite_health_score(
        100, 1.0, 100, True,
        drift_score=20, staleness_score=None,
    )
    assert "drift" in bd["weights"]
    assert "staleness" not in bd["weights"]
    # raw = (30+50+20+2) / 1.10 = 102/1.10 ≈ 92.7 → 93
    assert 90 <= score <= 95


def test_composite_missing_runtime_does_not_crash(radar):
    """Runtime ratio=None triggers weight redistribution; new dims still work."""
    score, bd = radar._composite_health_score(
        80, None, 100, True, drift_score=80, staleness_score=80,
    )
    assert "runtime" not in bd["weights"]
    assert bd["weights"]["governance"] == 0.8
    assert bd["weights"]["drift"] == 0.10
    assert bd["weights"]["staleness"] == 0.10


def test_composite_feedback_cap_still_works_with_new_dims(radar):
    """feedback_alive=False still caps at 50 even with new dims."""
    score, _bd = radar._composite_health_score(
        100, 1.0, 100, False, drift_score=100, staleness_score=100,
    )
    assert score <= 50


# ---------------------------------------------------------------------------
# Drift collector
# ---------------------------------------------------------------------------


def test_collect_drift_health_returns_none_when_tool_missing(radar, tmp_path):
    """Tool path absent → (None, {}); graceful no-op."""
    fake_root = tmp_path / "no_drift_tool"
    fake_root.mkdir()
    score, detail = radar._collect_drift_health(fake_root)
    assert score is None
    assert detail == {}


def test_collect_drift_health_returns_100_when_all_pass(radar, tmp_path, monkeypatch):
    """Mock drift-sweep.py to emit all-pass JSON → score=100."""
    fake_root = tmp_path
    tool_dir = fake_root / "bin" / "gac"
    tool_dir.mkdir(parents=True)
    # Create the path so is_file() check passes
    tool = tool_dir / "drift-sweep.py"
    tool.write_text("# stub")

    fake_result = {
        "summary": {"pass": 16, "fail": 0, "skip": 0, "total": 16},
        "results": [],
    }
    fake_stdout = _json.dumps(fake_result)

    class _FakeCompleted:
        returncode = 0
        stdout = fake_stdout

    def fake_run(*args, **kw):
        return _FakeCompleted()

    monkeypatch.setattr("subprocess.run", fake_run)

    score, detail = radar._collect_drift_health(fake_root)
    assert score == 100
    assert detail["pass"] == 16
    assert detail["fail"] == 0
    assert detail["source"] == "drift-sweep"


def test_collect_drift_health_deducts_on_failures(radar, tmp_path, monkeypatch):
    """Each fail drops 15 points; 2 fails → 70."""
    fake_root = tmp_path
    tool_dir = fake_root / "bin" / "gac"
    tool_dir.mkdir(parents=True)
    (tool_dir / "drift-sweep.py").write_text("# stub")

    fake_result = {"summary": {"pass": 14, "fail": 2, "skip": 0, "total": 16}}

    class _FakeCompleted:
        returncode = 0
        stdout = _json.dumps(fake_result)

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _FakeCompleted())

    score, detail = radar._collect_drift_health(fake_root)
    assert score == 70  # 100 - 15*2
    assert detail["fail"] == 2


def test_collect_drift_health_handles_subprocess_error(radar, tmp_path, monkeypatch):
    """Non-JSON stdout or non-zero exit → (None, {error: ...})."""
    fake_root = tmp_path
    tool_dir = fake_root / "bin" / "gac"
    tool_dir.mkdir(parents=True)
    (tool_dir / "drift-sweep.py").write_text("# stub")

    class _FakeCompleted:
        returncode = 2
        stdout = "garbage output"

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _FakeCompleted())

    score, detail = radar._collect_drift_health(fake_root)
    assert score is None
    assert "error" in detail


# ---------------------------------------------------------------------------
# KB staleness collector
# ---------------------------------------------------------------------------


def test_collect_kb_staleness_returns_none_when_tool_missing(radar, tmp_path):
    """Tool path absent → (None, {}); graceful no-op."""
    fake_root = tmp_path / "no_kb_tool"
    fake_root.mkdir()
    score, detail = radar._collect_kb_staleness(fake_root)
    assert score is None
    assert detail == {}


def test_collect_kb_staleness_penalises_stale_and_issues(radar, tmp_path, monkeypatch):
    """stale=98/492 + issues=195 → score≈50."""
    fake_root = tmp_path
    kb_dir = fake_root / "bin" / "kb"
    kb_dir.mkdir(parents=True)
    (kb_dir / "staleness-check.py").write_text("# stub")

    fake_result = {
        "checked": 492,
        "clean": 394,
        "stale": 98,
        "total_issues": 195,
        "results": [],
    }

    class _FakeCompleted:
        returncode = 0
        stdout = _json.dumps(fake_result)

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _FakeCompleted())

    score, detail = radar._collect_kb_staleness(fake_root)
    # penalty = 50*(98/492) + 100*(195/492) = 9.96 + 39.63 = 49.59 → 100-49.59 ≈ 50
    assert 48 <= score <= 52
    assert detail["checked"] == 492
    assert detail["stale"] == 98
    assert detail["total_issues"] == 195
    assert detail["stale_ratio"] == pytest.approx(0.1992, abs=0.01)


def test_collect_kb_staleness_clean_workspace(radar, tmp_path, monkeypatch):
    """All clean → score=100."""
    fake_root = tmp_path
    kb_dir = fake_root / "bin" / "kb"
    kb_dir.mkdir(parents=True)
    (kb_dir / "staleness-check.py").write_text("# stub")

    fake_result = {
        "checked": 100,
        "clean": 100,
        "stale": 0,
        "total_issues": 0,
        "results": [],
    }

    class _FakeCompleted:
        returncode = 0
        stdout = _json.dumps(fake_result)

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _FakeCompleted())

    score, _ = radar._collect_kb_staleness(fake_root)
    assert score == 100


def test_collect_kb_staleness_floor_zero(radar, tmp_path, monkeypatch):
    """Massive issues → clamped to 0 (not negative)."""
    fake_root = tmp_path
    kb_dir = fake_root / "bin" / "kb"
    kb_dir.mkdir(parents=True)
    (kb_dir / "staleness-check.py").write_text("# stub")

    fake_result = {
        "checked": 10,
        "clean": 0,
        "stale": 10,
        "total_issues": 500,  # 50 issues/file → 5000 penalty
        "results": [],
    }

    class _FakeCompleted:
        returncode = 0
        stdout = _json.dumps(fake_result)

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _FakeCompleted())

    score, _ = radar._collect_kb_staleness(fake_root)
    assert score == 0


# ---------------------------------------------------------------------------
# History append: new fields
# ---------------------------------------------------------------------------


def test_append_history_includes_drift_and_staleness(radar, tmp_path):
    """Snapshot now carries drift_score + staleness_score fields."""
    health_yaml = tmp_path / "state/health.yaml"
    health_yaml.parent.mkdir(parents=True)
    health_yaml.write_text("generated_at: now\n")

    report = {
        "health_score": 90,
        "governance_anomaly_score": 100,
        "anomaly_count": 0,
        "service_online_ratio": 1.0,
        "freshness_score": 100,
        "drift_score": 85,
        "staleness_score": 50,
        "total_tasks": 6,
        "source": "test",
    }
    radar._append_health_history(health_yaml, report)

    history_file = tmp_path / "state/history/health.jsonl"
    record = _json.loads(history_file.read_text().strip())
    assert record["drift_score"] == 85
    assert record["staleness_score"] == 50


# ---------------------------------------------------------------------------
# T10-10: alignment_score (三方成熟度口径对齐)
# ---------------------------------------------------------------------------


def test_composite_with_alignment_score(radar):
    """alignment_score 0.10 权重集成, 不破坏其他维度."""
    score, bd = radar._composite_health_score(
        100, 1.0, 100, True,
        drift_score=100, staleness_score=100, alignment_score=80,
    )
    assert bd["weights"]["alignment"] == 0.10
    assert bd["contributions"]["alignment"] == 80 * 0.10
    # total_weight = 1.30; raw = (30+50+20+10+10+8)/1.30 = 128/1.30 ≈ 98
    assert 95 <= score <= 99


def test_composite_alignment_alone_misses_other_dims(radar):
    """Only alignment passed; drift/staleness omitted → still integrates."""
    score, bd = radar._composite_health_score(
        80, 1.0, 80, True,
        alignment_score=80, drift_score=None, staleness_score=None,
    )
    assert "alignment" in bd["weights"]
    assert "drift" not in bd["weights"]
    assert "staleness" not in bd["weights"]


def test_collect_alignment_score_returns_none_when_tool_missing(radar, tmp_path):
    """Tool path absent → (None, {}); graceful no-op."""
    fake_root = tmp_path / "no_align_tool"
    fake_root.mkdir()
    score, detail = radar._collect_alignment_score(fake_root)
    assert score is None
    assert detail == {}


def test_collect_alignment_score_parses_reconciliation(radar, tmp_path, monkeypatch):
    """Mock maturity-align.py to emit JSON; verify reconciliation_score parsed."""
    fake_root = tmp_path
    align_dir = fake_root / "bin" / "gac"
    align_dir.mkdir(parents=True)
    (align_dir / "maturity-align.py").write_text("# stub")

    fake_result = {
        "alignment": {
            "drift_detected": False,
            "reconciliation_score": 85.0,
            "normalised": {"compass_radar": 70, "maturity_scorecard": 75, "bet_ledger": 90},
            "high_dimension": "bet_ledger",
            "low_dimension": "compass_radar",
            "warnings": [],
        }
    }

    class _FakeCompleted:
        returncode = 0
        stdout = _json.dumps(fake_result)

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _FakeCompleted())

    score, detail = radar._collect_alignment_score(fake_root)
    assert score == 85
    assert detail["source"] == "maturity-align"
    assert detail["drift_detected"] is False
    assert detail["high_dimension"] == "bet_ledger"


def test_collect_alignment_score_handles_missing_alignment_block(radar, tmp_path, monkeypatch):
    """JSON missing 'alignment' → (None, error)."""
    fake_root = tmp_path
    align_dir = fake_root / "bin" / "gac"
    align_dir.mkdir(parents=True)
    (align_dir / "maturity-align.py").write_text("# stub")

    class _FakeCompleted:
        returncode = 0
        stdout = _json.dumps({"compass_radar": {}, "bet_ledger": {}, "maturity_scorecard": {}})

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _FakeCompleted())

    score, detail = radar._collect_alignment_score(fake_root)
    assert score is None
    assert "missing" in detail.get("error", "") or "json" in detail.get("error", "")


def test_append_history_includes_alignment_score(radar, tmp_path):
    """history.jsonl snapshot now carries alignment_score."""
    health_yaml = tmp_path / "state/health.yaml"
    health_yaml.parent.mkdir(parents=True)
    health_yaml.write_text("generated_at: now\n")

    report = {
        "health_score": 90,
        "governance_anomaly_score": 100,
        "anomaly_count": 0,
        "service_online_ratio": 1.0,
        "freshness_score": 100,
        "drift_score": 85,
        "staleness_score": 50,
        "alignment_score": 80,
        "total_tasks": 6,
        "source": "test",
    }
    radar._append_health_history(health_yaml, report)

    history_file = tmp_path / "state/history/health.jsonl"
    record = _json.loads(history_file.read_text().strip())
    assert record["alignment_score"] == 80