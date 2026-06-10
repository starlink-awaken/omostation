from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "governance-check.yml"


def test_governance_workflow_enforces_phase11_controls() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True) or {}
    pull_request_paths = triggers["pull_request"]["paths"]
    job = workflow["jobs"]["governance-validate"]
    steps = job["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert ".github/workflows/governance-check.yml" in pull_request_paths
    assert "bin/verify-omo.sh" in pull_request_paths
    assert job.get("continue-on-error") in (False, None)
    assert "bash bin/verify-omo.sh" in commands
    assert "bash scripts/check-system-consistency.sh" in commands
