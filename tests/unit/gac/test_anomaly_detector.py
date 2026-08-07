import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "anomaly-detector.py"


def run_detector(args: list[str] | None = None, metrics_content: str | None = None, metrics_file: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    if metrics_file:
        cmd.extend(["--metrics-file", str(metrics_file)])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, input=metrics_content)


class TestAnomalyDetector:
    def test_no_anomalies_when_stable(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [{"check": f"check-{i}", "duration_ms": 10.0, "timestamp": f"2026-01-01T00:00:{i:02d}Z", "ok": True, "reason": "ok"} for i in range(10)]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        result = run_detector(["--window", "10", "--z-threshold", "2.0"], metrics_file=metrics_file)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["anomaly_count"] == 0

    def test_detects_spike(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [{"check": "check-x", "duration_ms": 10.0, "timestamp": f"2026-01-01T00:00:{i:02d}Z", "ok": True, "reason": "ok"} for i in range(9)]
        entries.append({"check": "check-x", "duration_ms": 1000.0, "timestamp": "2026-01-01T00:00:09Z", "ok": True, "reason": "slow"})
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        result = run_detector(["--window", "10", "--z-threshold", "2.0"], metrics_file=metrics_file)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["anomaly_count"] >= 1
        assert data["anomalies"][-1]["check"] == "check-x"
        assert data["anomalies"][-1]["duration_ms"] == 1000.0

    def test_empty_file(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        result = run_detector(["--window", "10"], metrics_file=metrics_file)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["metrics_entries"] == 0
        assert data["anomaly_count"] == 0

    def test_window_truncation(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [{"check": "check-w", "duration_ms": float(i), "timestamp": f"2026-01-01T00:00:{i:02d}Z", "ok": True, "reason": "ok"} for i in range(20)]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        result = run_detector(["--window", "5"], metrics_file=metrics_file)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["metrics_entries"] == 5
