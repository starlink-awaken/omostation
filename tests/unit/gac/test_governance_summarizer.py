import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "governance-summarizer.py"


def run_summarizer(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestGovernanceSummarizer:
    def test_summarize_pass(self, tmp_path: Path):
        report = {
            "ok": True,
            "scope": "staged",
            "run_id": "run-123",
            "checks": [{"name": "check-a", "ok": True, "duration_ms": 10}],
            "hard_fails": [],
            "soft_warns": [],
            "finding_topics": [],
            "change_lane_files": ["README.md"],
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")
        result = run_summarizer(["--report", str(report_file)])
        assert result.returncode == 0
        assert "# Governance Gate Summary" in result.stdout
        assert "PASS" in result.stdout

    def test_summarize_fail(self, tmp_path: Path):
        report = {
            "ok": False,
            "scope": "staged",
            "checks": [
                {"name": "check-a", "ok": True, "duration_ms": 10},
                {"name": "check-b", "ok": False, "stderr": "error details", "stdout": ""},
            ],
            "hard_fails": [{"name": "check-b", "stderr": "error details", "stdout": ""}],
            "soft_warns": [],
            "finding_topics": [
                {"severity": "error", "topic": "test-topic", "summary": "something broke"}
            ],
            "change_lane_files": [],
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")
        result = run_summarizer(["--report", str(report_file)])
        assert result.returncode == 0
        assert "FAIL" in result.stdout
        assert "## Hard Failures" in result.stdout
        assert "check-b" in result.stdout

    def test_invalid_json(self, tmp_path: Path):
        report_file = tmp_path / "bad.json"
        report_file.write_text("not json", encoding="utf-8")
        result = run_summarizer(["--report", str(report_file)])
        assert result.returncode == 1

    def test_missing_report(self, tmp_path: Path):
        result = run_summarizer(["--report", str(tmp_path / "missing.json")])
        assert result.returncode == 1

    def test_llm_endpoint_ignored_on_failure(self, tmp_path: Path):
        report = {"ok": True, "scope": "staged", "checks": [], "hard_fails": [], "soft_warns": [], "finding_topics": [], "change_lane_files": []}
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")
        result = run_summarizer(["--report", str(report_file), "--llm-endpoint", "http://localhost:9999"])
        assert result.returncode == 0
        assert "# Governance Gate Summary" in result.stdout
