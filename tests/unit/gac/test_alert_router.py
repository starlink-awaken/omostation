import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "alert-router.py"


def run_router(args: list[str] | None = None, anomaly_content: str | None = None, anomaly_file: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    if anomaly_file:
        cmd.extend(["--anomaly-file", str(anomaly_file)])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, input=anomaly_content)


class TestAlertRouter:
    def test_dry_run_empty(self, tmp_path: Path):
        anomaly_file = tmp_path / "anomaly-events.jsonl"
        result = run_router(["--dry-run", "--window", "5"], anomaly_file=anomaly_file)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["routed"] == 0
        assert data["anomalies"] == []

    def test_dry_run_returns_anomalies(self, tmp_path: Path):
        anomaly_file = tmp_path / "anomaly-events.jsonl"
        anomaly_file.write_text(json.dumps({"check": "check-x", "duration_ms": 1000.0, "z": 3.0, "timestamp": "2026-01-01T00:00:00Z"}) + "\n", encoding="utf-8")
        result = run_router(["--dry-run", "--window", "5"], anomaly_file=anomaly_file)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["routed"] == 0
        assert len(data["anomalies"]) == 1
        assert data["anomalies"][0]["check"] == "check-x"

    def test_routes_to_log_when_enabled(self, tmp_path: Path):
        anomaly_file = tmp_path / "anomaly-events.jsonl"
        log_file = tmp_path / "alerts.log"
        config_file = tmp_path / "governance-alerts.yaml"
        config_file.write_text(
            "channels:\n  log:\n    enabled: true\n    path: " + str(log_file) + "\n",
            encoding="utf-8",
        )
        anomaly_file.write_text(json.dumps({"check": "check-x", "duration_ms": 1000.0, "z": 3.0}) + "\n", encoding="utf-8")
        result = run_router(["--config", str(config_file), "--window", "5"], anomaly_file=anomaly_file)
        assert result.returncode == 0
        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert "check-x" in lines[0]

    def test_skips_disabled_channels(self, tmp_path: Path):
        anomaly_file = tmp_path / "anomaly-events.jsonl"
        log_file = tmp_path / "alerts.log"
        config_file = tmp_path / "governance-alerts.yaml"
        config_file.write_text(
            "channels:\n  log:\n    enabled: false\n    path: " + str(log_file) + "\n",
            encoding="utf-8",
        )
        anomaly_file.write_text(json.dumps({"check": "check-x", "duration_ms": 1000.0, "z": 3.0}) + "\n", encoding="utf-8")
        result = run_router(["--config", str(config_file), "--window", "5"], anomaly_file=anomaly_file)
        assert result.returncode == 0
        assert not log_file.exists()
