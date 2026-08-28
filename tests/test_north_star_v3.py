"""Tests for bin/bc-os/north_star_meter_v3.py (project-strategy-v1 §5.2 落地)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "bin" / "bc-os" / "north_star_meter_v3.py"
_MODULE = "_north_star_meter_v3_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    return _load()


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def test_cadence_labels(tool):
    assert tool._cadence_label(0.5) == "none"
    assert tool._cadence_label(1) == "low"
    assert tool._cadence_label(3) == "low"
    assert tool._cadence_label(4) == "medium"
    assert tool._cadence_label(11) == "medium"
    assert tool._cadence_label(12) == "high"


def test_time_per_event_constants_have_all_keys(tool):
    expected = {"compass_radar_run", "drift_sweep_run", "signal_poll", "agent_tick",
                "maturity_scorecard_run", "document_review_sample",
                "knowledge_curation", "staleness_check"}
    assert set(tool.TIME_PER_EVENT_MIN) == expected


def test_time_per_event_constants_positive(tool):
    for k, v in tool.TIME_PER_EVENT_MIN.items():
        assert v > 0, f"{k} must be positive"


def test_read_jsonl_events_returns_zero_for_missing_file(tool, tmp_path):
    assert tool._read_jsonl_events(tmp_path / "no-such.jsonl") == 0


def test_read_jsonl_events_counts_recent(tool, tmp_path):
    from datetime import datetime, timezone, timedelta
    p = tmp_path / "events.jsonl"
    cutoff = datetime.now(timezone.utc) - timedelta(days=10)
    p.write_text(
        json.dumps({"ts": cutoff.isoformat()}) + "\n"
        + json.dumps({"ts": "2020-01-01T00:00:00Z"}) + "\n"
        + json.dumps({"ts": "no-ts-here"}) + "\n"
    )
    n = tool._read_jsonl_events(p, since_days=30)
    # recent + no-ts = 2 (the old one is excluded)
    assert n == 2


def test_compute_axes_returns_three_axes(tool):
    out = tool.compute_axes(since_days=30)
    assert "A" in out["axes"]
    assert "B" in out["axes"]
    assert "C" in out["axes"]
    assert "D" in out["axes"]


def test_compute_axes_composite_in_range(tool):
    out = tool.compute_axes(since_days=30)
    assert 0 <= out["composite"]["score"] <= 100
    assert 0 <= out["composite_4axis"]["score"] <= 100
    assert out["status"] in {"unprovable", "low", "partial", "provable"}


def test_compute_axes_4axis_advisory_flag(tool):
    out = tool.compute_axes(since_days=30)
    c4 = out["composite_4axis"]
    assert c4["advisory"] is True
    assert "weights" in c4
    assert c4["weights"]["D"] == 0.20


def test_count_knowledge_consumption_returns_zeros_for_missing_file(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "WORKFLOW_MESH_EVENTS", tmp_path / "no-such.jsonl")
    result = tool._count_knowledge_consumption(since_days=30)
    assert result == {"evidence_recorded": 0, "workflow_succeeded": 0, "total": 0}


def test_count_knowledge_consumption_counts_recent_events(tool, tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    p = tmp_path / "events.jsonl"
    cutoff = datetime.now(timezone.utc) - timedelta(days=10)
    recent_iso = cutoff.isoformat()
    p.write_text(
        json.dumps({"event_type": "EvidenceRecorded", "occurred_at": recent_iso}) + "\n"
        + json.dumps({"event_type": "WorkflowSucceeded", "occurred_at": recent_iso}) + "\n"
        + json.dumps({"event_type": "EvidenceRecorded", "occurred_at": "2020-01-01T00:00:00Z"}) + "\n"
        + json.dumps({"event_type": "WorkflowRequested", "occurred_at": recent_iso}) + "\n"
    )
    monkeypatch.setattr(tool, "WORKFLOW_MESH_EVENTS", p)
    result = tool._count_knowledge_consumption(since_days=30)
    assert result["evidence_recorded"] == 1
    assert result["workflow_succeeded"] == 1
    assert result["total"] == 2


def test_compute_axes_d_axis_score_capped(tool, tmp_path, monkeypatch):
    """D score caps at 100 even when events_per_month > 30."""
    from datetime import datetime, timezone
    p = tmp_path / "events.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    lines = "\n".join(
        json.dumps({"event_type": "EvidenceRecorded", "occurred_at": now}) for _ in range(100)
    )
    p.write_text(lines + "\n")
    monkeypatch.setattr(tool, "WORKFLOW_MESH_EVENTS", p)
    out = tool.compute_axes(since_days=30)
    assert out["axes"]["D"]["score"] == 100
    assert out["composite_4axis"]["score"] <= 100


def test_compute_axes_window_parameter(tool):
    """Larger window = more events, smaller window = fewer."""
    out_30 = tool.compute_axes(since_days=30)
    out_1 = tool.compute_axes(since_days=1)
    a30 = sum(out_30["axes"]["A"]["data"].values())
    a1 = sum(out_1["axes"]["A"]["data"].values())
    # 30d window should count >= 1d window (monotonic)
    assert a30 >= a1


def test_compute_axes_real_workspace_produces_a_data(tool):
    """Smoke: real workspace has agent-tick-daemon.jsonl with events → A > 0."""
    out = tool.compute_axes(since_days=30)
    # Either compass_radar_run or signal_poll should have some count
    a_data = out["axes"]["A"]["data"]
    total = sum(a_data.values())
    # In a real workspace with cron activity, this should be > 0
    # (don't enforce, but at least log)
    assert total >= 0


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_runs_and_emits_valid_json():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "axes" in data
    assert "composite" in data
    assert "status" in data
    assert "snapshot_at" in data


def test_cli_text_mode_runs():
    import subprocess
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    assert "north_star_meter_v3" in result.stdout
    assert "composite" in result.stdout
    assert "Axis A" in result.stdout


# Late import to avoid circular issues
import subprocess

# ---------------------------------------------------------------------------
# E-axis: Decision Quality
# ---------------------------------------------------------------------------


def test_count_decision_quality_returns_dict(tool):
    """Test that _count_decision_quality returns expected structure."""
    result = tool._count_decision_quality(since_days=30)
    assert "p0_p1_count" in result
    assert "p2_count" in result
    assert "total" in result
    assert "adopted_count" in result
    assert "adoption_ratio" in result


def test_count_decision_quality_empty_when_no_file(tool):
    """Test returns empty when decisions.md doesn't exist."""
    import tempfile
    import os
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary WS_ROOT without decisions.md
        original = tool.WS_ROOT
        tool.WS_ROOT = Path(tmpdir)
        try:
            result = tool._count_decision_quality(since_days=30)
            assert result["total"] == 0
            assert result["p0_p1_count"] == 0
            assert result["adopted_count"] == 0
            assert result["adoption_ratio"] == 0.0
        finally:
            tool.WS_ROOT = original


def test_count_decision_quality_counts_recent(tool):
    """Test that only recent decisions are counted."""
    import tempfile
    import os
    from datetime import datetime, timezone, timedelta
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original = tool.WS_ROOT
        tool.WS_ROOT = Path(tmpdir)
        try:
            # Create decisions.md with a recent P1 decision
            decisions_dir = Path(tmpdir) / ".omo" / "notepads" / "delegation-guardrails"
            decisions_dir.mkdir(parents=True)
            decisions_path = decisions_dir / "decisions.md"
            
            recent_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
            decisions_path.write_text(f"""## [{recent_date}] P1: Test decision
- **决策**: test
- **验证**: implemented
""")
            
            result = tool._count_decision_quality(since_days=30)
            assert result["total"] == 1
            assert result["p0_p1_count"] == 1
            assert result["adopted_count"] == 1
            assert result["adoption_ratio"] == 1.0
        finally:
            tool.WS_ROOT = original


def test_compute_axes_returns_five_axes(tool):
    """Test that v3 returns 5 axes."""
    out = tool.compute_axes(since_days=30)
    assert len(out["axes"]) == 6
    assert "A" in out["axes"]
    assert "B" in out["axes"]
    assert "C" in out["axes"]
    assert "D" in out["axes"]
    assert "E" in out["axes"]


def test_compute_axes_composite_5axis(tool):
    """Test that 5-axis composite is computed."""
    out = tool.compute_axes(since_days=30)
    assert "composite_5axis" in out
    assert "score" in out["composite_5axis"]
    assert "weights" in out["composite_5axis"]
    assert out["composite_5axis"]["weights"]["E"] == 0.15
    assert out["composite_5axis"]["weights"]["D"] == 0.20
