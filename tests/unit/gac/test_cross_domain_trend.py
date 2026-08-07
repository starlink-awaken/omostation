import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "cross-domain-trend.py"


def run_trend(args: list[str] | None = None, registry_content: str | None = None, registry_file: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    if registry_file:
        cmd.extend(["--registry", str(registry_file)])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, input=registry_content)


class TestCrossDomainTrend:
    def test_analyze_governance_trend(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {"check": "check-a", "duration_ms": 10.0, "timestamp": f"2026-01-0{i}T00:00:00Z", "ok": True, "reason": "ok"}
            for i in range(1, 6)
        ]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        reg = tmp_path / "trend-fusion.yaml"
        reg.write_text(
            f"""version: 1
domains:
  governance:
    description: test
    source: {metrics_file}
    adapter: governance-trend-adapter
    enabled: true
    metrics: [gate_pass_rate]
fusion:
  weights:
    governance: 1.0
  alert_threshold: 0.3
""",
            encoding="utf-8",
        )
        result = run_trend(["--window", "5"], registry_file=reg)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["fusion"]["trend"] == "healthy"
        assert "governance" in data["domains"]

    def test_disabled_domain_skipped(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        metrics_file.write_text(
            json.dumps({"check": "check-a", "duration_ms": 10.0, "timestamp": "2026-01-01T00:00:00Z", "ok": True}) + "\n",
            encoding="utf-8",
        )
        reg = tmp_path / "trend-fusion.yaml"
        reg.write_text(
            f"""version: 1
domains:
  governance:
    description: test
    source: {metrics_file}
    enabled: false
    metrics: []
fusion:
  weights:
    governance: 1.0
""",
            encoding="utf-8",
        )
        result = run_trend(["--window", "5"], registry_file=reg)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["domains"] == {}

    def test_declining_trend_detected(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {"check": "check-a", "duration_ms": 10.0, "timestamp": f"2026-01-0{i}T00:00:00Z", "ok": i < 3, "reason": "fail"}
            for i in range(1, 6)
        ]
        metrics_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        reg = tmp_path / "trend-fusion.yaml"
        reg.write_text(
            f"""version: 1
domains:
  governance:
    description: test
    source: {metrics_file}
    adapter: governance-trend-adapter
    enabled: true
    metrics: [gate_pass_rate]
fusion:
  weights:
    governance: 1.0
  alert_threshold: 0.3
""",
            encoding="utf-8",
        )
        result = run_trend(["--window", "5"], registry_file=reg)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        gov = data["domains"].get("governance", {})
        assert gov.get("trend") == "declining"
