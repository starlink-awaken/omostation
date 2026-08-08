import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "debt-predictor.py"


def run_predictor(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestDebtPredictor:
    def test_predict_insufficient_history(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        debt_dir = tmp_path / "empty-debt"
        debt_dir.mkdir(parents=True)
        result = run_predictor([
            "--threshold", "10",
            "--metrics-file", str(metrics_file),
            "--debt-dir", str(debt_dir),
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "error" in data["prediction"]

    def test_predict_with_history(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        for i in range(10):
            with metrics_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"timestamp": f"2026-08-0{i+1}T00:00:00Z", "check": "check-a", "ok": True, "duration_ms": 10}) + "\n")
        result = run_predictor(["--threshold", "100", "--metrics-file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "prediction" in data

    def test_snapshot_counts_debt_items(self, tmp_path: Path):
        debt_dir = tmp_path / "debt" / "items"
        debt_dir.mkdir(parents=True)
        (debt_dir / "DEBT-1.yaml").write_text("id: DEBT-1\nstatus: open\nseverity: high\n", encoding="utf-8")
        (debt_dir / "DEBT-2.yaml").write_text("id: DEBT-2\nstatus: closed\nseverity: low\n", encoding="utf-8")
        result = run_predictor(["--threshold", "10", "--debt-dir", str(debt_dir)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["snapshot"]["total"] == 2
        assert data["snapshot"]["by_status"]["open"] == 1
        assert data["snapshot"]["by_severity"]["high"] == 1
