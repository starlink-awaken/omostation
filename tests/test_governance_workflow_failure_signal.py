from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "governance-check.yml"


def _steps() -> list[dict[str, object]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["governance-verify"]["steps"]


def _step(name: str) -> dict[str, object]:
    return next(step for step in _steps() if step.get("name") == name)


def test_failure_signal_step_has_failure_safe_durable_structure() -> None:
    signal = _step("Emit failure signal on break")
    artifact = _step("Upload governance failure signal")

    assert signal["if"] == "failure()"
    assert signal["continue-on-error"] is True
    assert signal["env"] == {
        "FAILURE_LOG": "${{ runner.temp }}/omo-events.jsonl",
        "FAILURE_REF": "${{ github.ref }}",
        "FAILURE_SHA": "${{ github.sha }}",
        "FAILURE_RUN_URL": (
            "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
        ),
    }
    assert artifact["if"] == "failure()"
    assert artifact["uses"] == "actions/upload-artifact@v4"
    assert artifact["with"] == {
        "name": "governance-verify-failure-signal-${{ github.run_id }}",
        "path": "${{ runner.temp }}/omo-events.jsonl",
        "if-no-files-found": "warn",
        "retention-days": 14,
    }


def test_failure_signal_shell_emits_uploadable_jsonl_and_summary(tmp_path: Path) -> None:
    signal = _step("Emit failure signal on break")
    script = str(signal["run"]).replace("${{ github.run_id }}", "123")
    event_log = tmp_path / "omo-events.jsonl"
    summary = tmp_path / "summary.md"
    env = os.environ.copy()
    env.update(
        {
            "FAILURE_LOG": str(event_log),
            "FAILURE_REF": "refs/heads/test",
            "FAILURE_SHA": "deadbeef",
            "FAILURE_RUN_URL": "https://example.invalid/actions/runs/123",
            "GITHUB_STEP_SUMMARY": str(summary),
        }
    )

    completed = subprocess.run(
        ["bash", "-eu", "-o", "pipefail", "-c", script],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    records = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["kind"] == "governance_verify_failed"
    assert records[0]["source"] == "ci/governance-check.yml"
    assert json.loads(records[0]["payload"]) == {
        "ref": "refs/heads/test",
        "sha": "deadbeef",
        "run_url": "https://example.invalid/actions/runs/123",
    }
    summary_text = summary.read_text(encoding="utf-8")
    assert "emitter exit: `0`" in summary_text
    assert "governance-verify-failure-signal-123" in summary_text
