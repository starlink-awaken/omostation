from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.phase3_acceptance import AcceptanceRun, build_markdown_report, run_suite  # noqa: E402


def test_run_suite_collects_counts_and_category(tmp_path, monkeypatch):
    def _fake_run(command, cwd, capture_output, text, timeout, env):
        assert cwd == ROOT / "projects" / "kairon"
        assert env["PHASE3_ACCEPTANCE"] == "1"
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="4 passed\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = run_suite(
        AcceptanceRun(
            name="wksp",
            category="workspace",
            cwd=ROOT / "projects" / "kairon",
            command=[sys.executable, "-m", "pytest", "packages/wksp/src/wksp/tests/test_e2e_journey.py", "-q"],
            timeout=120,
            env={"PHASE3_ACCEPTANCE": "1"},
        )
    )

    assert result["name"] == "wksp"
    assert result["category"] == "workspace"
    assert result["returncode"] == 0
    assert result["passed"] == 4
    assert result["failed"] == 0


def test_run_suite_marks_missing_binary_as_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise FileNotFoundError("bun not found")

    monkeypatch.setattr(subprocess, "run", _raise)

    result = run_suite(
        AcceptanceRun(
            name="gbrain-recovery",
            category="recovery",
            cwd=ROOT / "projects" / "gbrain",
            command=["bun", "test", "test/e2e/worker-abort-recovery.test.ts"],
            timeout=120,
        )
    )

    assert result["returncode"] == 127
    assert result["failed"] == 1
    assert "bun not found" in str(result["output"])


def test_run_suite_merges_custom_env_with_process_env(monkeypatch):
    def _fake_run(command, cwd, capture_output, text, timeout, env):
        assert env["PHASE3_ACCEPTANCE"] == "1"
        assert "PATH" in env
        return subprocess.CompletedProcess(command, 0, stdout="1 passed\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = run_suite(
        AcceptanceRun(
            name="env-check",
            category="capabilities",
            cwd=ROOT,
            command=[sys.executable, "-m", "pytest", "-q"],
            env={"PHASE3_ACCEPTANCE": "1"},
        )
    )

    assert result["returncode"] == 0


def test_build_markdown_report_groups_summary():
    report = build_markdown_report(
        [
            {
                "name": "wksp",
                "category": "workspace",
                "returncode": 0,
                "passed": 10,
                "failed": 0,
                "command": "pytest wksp",
                "cwd": "/repo/projects/kairon",
                "output": "10 passed",
            },
            {
                "name": "gbrain-recovery",
                "category": "recovery",
                "returncode": 1,
                "passed": 2,
                "failed": 1,
                "command": "bun test recovery",
                "cwd": "/repo/projects/gbrain",
                "output": "1 failed",
            },
        ]
    )

    assert "# Phase 3 acceptance report" in report
    assert "| workspace | wksp | PASS | 10 | 0 |" in report
    assert "| recovery | gbrain-recovery | FAIL | 2 | 1 |" in report
    assert "Totals: passed=12 failed=1 suites=2" in report
