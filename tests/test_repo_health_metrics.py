"""Tests for repo-health-metrics (BET-Y1Q4-T10-130): trend, alerts, report."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "repo_health_metrics",
    Path(__file__).resolve().parents[1] / "bin" / "gac" / "repo-health-metrics.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_collect_shape():
    cur = _mod.collect()
    for key in ("local_branches", "remote_branches", "tags", "worktrees",
                "loose_objects", "dangling_remote_branches", "gitlink_drift", "ts"):
        assert key in cur, f"missing {key}"
    assert all(isinstance(cur[k], int) for k in list(_mod.ALERTS))


def test_trend_arrows():
    prev = {"loose_objects": 500, "worktrees": 10, "dangling_remote_branches": 1, "gitlink_drift": 0}
    cur = {"loose_objects": 1200, "worktrees": 10, "dangling_remote_branches": 0, "gitlink_drift": 0}
    trend = _mod._trend(cur, prev)
    assert trend["loose_objects"] == "↑"
    assert trend["worktrees"] == "→"
    assert trend["dangling_remote_branches"] == "↓"


def test_alerts_thresholds():
    cur = {"loose_objects": 1500, "worktrees": 30, "dangling_remote_branches": 6, "gitlink_drift": 1}
    alerts = _mod._alerts(cur)
    assert len(alerts) == 3
    assert any("loose_objects=1500" in a for a in alerts)


def test_report_contains_alert_section(tmp_path: Path):
    cur = _mod.collect()
    md = _mod.render_report(cur, None)
    assert "# 仓库健康度周报" in md
    assert "## 当期指标" in md and "## 告警" in md


def test_snapshot_and_trend_roundtrip(tmp_path: Path):
    hist = tmp_path / "history.jsonl"
    first = dict(_mod.collect())
    _mod.snapshot(first, hist)
    prev = _mod._load_previous(hist)
    assert prev is not None and prev["ts"] == first["ts"]
    md = _mod.render_report(_mod.collect(), prev)
    assert "趋势对比基线" in md


def test_cli_end_to_end(tmp_path: Path):
    out = subprocess_run([sys.executable, str(Path(__file__).resolve().parents[1] / "bin" / "gac" / "repo-health-metrics.py"), "--json"])
    data = json.loads(out)
    assert data["schema"] == "gac.repo_health.v1"


def subprocess_run(cmd: list[str]) -> str:
    import subprocess
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res.stdout
