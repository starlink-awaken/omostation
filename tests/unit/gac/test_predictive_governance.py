import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "predictive-governance.py"


def run_predictor(args: list[str] | None = None, registry_content: str | None = None, registry_file: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    if registry_file:
        cmd.extend(["--registry", str(registry_file)])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, input=registry_content)


class TestPredictiveGovernance:
    def test_prediction_declining(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {"check": "check-a", "duration_ms": 10.0, "timestamp": f"2026-01-0{i}T00:00:00Z", "ok": True}
            for i in range(1, 4)
        ]
        entries.extend([
            {"check": "check-a", "duration_ms": 10.0, "timestamp": f"2026-01-0{i}T00:00:00Z", "ok": False}
            for i in range(4, 7)
        ])
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        reg = tmp_path / "predictive-governance.yaml"
        reg.write_text(
            """version: 1
model:
  method: linear_regression
  min_history: 3
  confidence_threshold: 0.7
features: []
recommendations:
  - trigger: gate_pass_rate_declining
    action: review_recent_changes
    priority: P1
    template: "gate pass rate declining ({value}%/day). Review recent commits for regression."
  - trigger: stable_healthy
    action: maintain_current_practices
    priority: P3
    template: "governance metrics stable and healthy. Maintain current practices."
simulation:
  threshold_adjustments: []
output:
  format: json
  path: .omo/state/runtime/predictive-governance.json
""",
            encoding="utf-8",
        )
        result = run_predictor(["--registry", str(reg), "--metrics-file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "prediction" in data
        assert "recommendations" in data

    def test_prediction_insufficient_history(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        metrics_file.write_text(
            json.dumps({"check": "check-a", "duration_ms": 10.0, "timestamp": "2026-01-01T00:00:00Z", "ok": True}) + "\n",
            encoding="utf-8",
        )
        reg = tmp_path / "predictive-governance.yaml"
        reg.write_text(
            """version: 1
model:
  method: linear_regression
  min_history: 5
  confidence_threshold: 0.7
features: []
recommendations: []
simulation:
  threshold_adjustments: []
output:
  format: json
  path: .omo/state/runtime/predictive-governance.json
""",
            encoding="utf-8",
        )
        result = run_predictor(["--registry", str(reg), "--metrics-file", str(metrics_file)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "error" in data

    def test_simulate_threshold_safe(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {"check": "check-x", "duration_ms": 10.0, "timestamp": f"2026-01-01T00:00:{i:02d}Z", "ok": True}
            for i in range(5)
        ]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        reg = tmp_path / "predictive-governance.yaml"
        reg.write_text(
            """version: 1
model:
  method: linear_regression
  min_history: 3
  confidence_threshold: 0.7
features: []
recommendations: []
simulation:
  threshold_adjustments: []
output:
  format: json
  path: .omo/state/runtime/predictive-governance.json
""",
            encoding="utf-8",
        )
        result = run_predictor(["--registry", str(reg), "--metrics-file", str(metrics_file), "--simulate-threshold", "10", "--check", "check-x"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["would_trigger"] is False

    def test_simulate_threshold_triggers(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {"check": "check-x", "duration_ms": 10.0, "timestamp": f"2026-01-01T00:00:{i:02d}Z", "ok": i < 4}
            for i in range(5)
        ]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        reg = tmp_path / "predictive-governance.yaml"
        reg.write_text(
            """version: 1
model:
  method: linear_regression
  min_history: 3
  confidence_threshold: 0.7
features: []
recommendations: []
simulation:
  threshold_adjustments: []
output:
  format: json
  path: .omo/state/runtime/predictive-governance.json
""",
            encoding="utf-8",
        )
        result = run_predictor(["--registry", str(reg), "--metrics-file", str(metrics_file), "--simulate-threshold", "0", "--check", "check-x"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["would_trigger"] is True
