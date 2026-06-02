from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_canonical_runner_exists_and_keeps_stage_order() -> None:
    script = _read("bin/verify-omo.sh")

    sync_cmd = "python3 scripts/sync_omo_state.py --omo-dir .omo"
    validate_cmd = "python3 scripts/omo_worker.py task validate --all-active"
    test_cmd = "python3 -m pytest .omo/tests -q"

    assert "#!/usr/bin/env bash" in script
    assert "set -euo pipefail" in script
    assert sync_cmd in script
    assert validate_cmd in script
    assert test_cmd in script
    assert script.index(sync_cmd) < script.index(validate_cmd) < script.index(test_cmd)


def test_makefile_delegates_to_canonical_runner() -> None:
    makefile = _read("Makefile")

    assert "governance-verify:" in makefile
    assert "\tbash bin/verify-omo.sh" in makefile
    assert "governance-check: governance-verify governance-index-check" in makefile


def test_governance_workflow_uses_canonical_runner() -> None:
    workflow = _read(".github/workflows/governance-check.yml")

    assert "- name: Canonical .omo verification" in workflow
    assert "run: bash bin/verify-omo.sh" in workflow


def test_omo_agent_documents_canonical_verification_command() -> None:
    agent = _read(".omo/AGENT.md")

    assert "canonical `.omo` verification command" in agent.lower()
    assert "`bash bin/verify-omo.sh`" in agent
    assert "`make governance-verify`" in agent
    assert "partial checks only" in agent
