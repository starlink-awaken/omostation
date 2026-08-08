import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "adaptive-gate.py"


def run_adaptive(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestAdaptiveGate:
    def test_recommend_threshold_basic(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        for i in range(20):
            ok = i < 18
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "bin" / "gac" / "metrics-store.py"),
                    "append",
                    "--check",
                    "check-a",
                    "--ok",
                    str(ok).lower(),
                    "--duration-ms",
                    str(10 + i),
                    "--file",
                    str(metrics_file),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
        result = run_adaptive(["--check", "check-a", "--window", "20", "--file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["check"] == "check-a"
        assert data["window"] == 20
        assert data["recommended_warn_threshold"] >= 3
        assert data["pass_rate"] == pytest.approx(0.9, abs=0.01)

    def test_anomaly_detection(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        for i in range(10):
            duration = 10 if i < 8 else 1000
            ok = i < 9
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "bin" / "gac" / "metrics-store.py"),
                    "append",
                    "--check",
                    "check-b",
                    "--ok",
                    str(ok).lower(),
                    "--duration-ms",
                    str(duration),
                    "--file",
                    str(metrics_file),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
        result = run_adaptive(["--check", "check-b", "--window", "10", "--anomalies", "--file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["anomalies"]) >= 1

    def test_summary_empty_file(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        result = run_adaptive(["--summary", "--file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_no_metrics_returns_error(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        result = run_adaptive(["--check", "missing", "--file", str(metrics_file)])
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_window_respected(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        for i in range(10):
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "bin" / "gac" / "metrics-store.py"),
                    "append",
                    "--check",
                    "check-c",
                    "--ok",
                    "true",
                    "--duration-ms",
                    str(i),
                    "--file",
                    str(metrics_file),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
        result = run_adaptive(["--check", "check-c", "--window", "5", "--file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["window"] == 5
