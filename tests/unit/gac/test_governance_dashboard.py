import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "governance-dashboard.py"


def run_dashboard(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestGovernanceDashboardMetrics:
    def test_metrics_dashboard_json_empty(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        result = run_dashboard(["--metrics-dashboard", "--metrics-file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_entries"] == 0
        assert data["overall_pass_rate"] == 0.0
        assert data["checks"] == []

    def test_metrics_dashboard_json_with_entries(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {"check": "check-a", "duration_ms": 10.0, "timestamp": "2026-01-01T00:00:00Z", "ok": True, "reason": "ok"},
            {"check": "check-a", "duration_ms": 20.0, "timestamp": "2026-01-01T00:00:01Z", "ok": True, "reason": "ok"},
            {"check": "check-b", "duration_ms": 30.0, "timestamp": "2026-01-01T00:00:02Z", "ok": False, "reason": "fail"},
        ]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        result = run_dashboard(["--metrics-dashboard", "--metrics-file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_entries"] == 3
        assert abs(data["overall_pass_rate"] - 2 / 3) < 0.001
        assert len(data["checks"]) == 2
        check_a = next(c for c in data["checks"] if c["check"] == "check-a")
        assert check_a["ok_count"] == 2
        assert check_a["fail_count"] == 0
        assert check_a["pass_rate"] == 1.0

    def test_metrics_dashboard_html_output(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        output_file = tmp_path / "dashboard.html"
        metrics_file.write_text(
            json.dumps({"check": "check-a", "duration_ms": 10.0, "timestamp": "2026-01-01T00:00:00Z", "ok": True, "reason": "ok"}) + "\n",
            encoding="utf-8",
        )
        result = run_dashboard(["--metrics-dashboard", "--metrics-file", str(metrics_file), "--output", str(output_file)])
        assert result.returncode == 0
        assert output_file.exists()
        html = output_file.read_text(encoding="utf-8")
        assert "Governance Metrics" in html
        assert "check-a" in html

    def test_metrics_dashboard_time_series(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {"check": "check-a", "duration_ms": 10.0, "timestamp": f"2026-01-0{i}T00:00:00Z", "ok": True, "reason": "ok"}
            for i in range(1, 4)
        ]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        result = run_dashboard(["--metrics-dashboard", "--metrics-file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "time_series" in data
        assert len(data["time_series"]) == 3
