from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_MODULE_PATH = ROOT / "bin" / "agent-workflow.py"
LANE_MODULE_PATH = ROOT / "bin" / "change-lane-check.py"


def _load_module_from_source(path: Path, name: str):
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__dict__["__file__"] = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _run_workflow(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(WORKFLOW_MODULE_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_agent_workflow_registry_lints() -> None:
    result = _run_workflow("lint", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["errors"] == []
    assert isinstance(report["warnings"], list)


def test_project_code_workflow_substitutes_project_context() -> None:
    result = _run_workflow("show", "project-code-change", "--project", "omo", "--json")

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)

    assert "project:omo" in plan["lock_scopes"]
    project_status = plan["phases"]["preflight"][1]
    assert project_status["cwd"] == "projects/omo"


def test_agent_workflow_doctor_runs_required_checks() -> None:
    result = _run_workflow("doctor", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    check_ids = {item["id"] for item in report["checks"]}
    assert report["ok"] is True
    assert "root-agent-workflow-list" in check_ids
    assert "cockpit-agent-workflow-list" in check_ids
    assert "omo-bridge-help" in check_ids


def test_start_run_dry_run_does_not_write_state() -> None:
    run_dir = ROOT / ".omo" / "_delivery" / "agent-workflows" / "runs"
    before = set(run_dir.glob("*.yaml")) if run_dir.exists() else set()
    result = _run_workflow(
        "start",
        "project-doc-change",
        "--actor",
        "test",
        "--objective",
        "dry-run test",
        "--dry-run",
        "--json",
    )
    after = set(run_dir.glob("*.yaml")) if run_dir.exists() else set()

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["status"] == "active"
    assert record["locks"] == []
    assert before == after


def test_start_handoff_close_writes_ledger_and_releases_locks(tmp_path: Path) -> None:
    registry = tmp_path / "agent-workflows.yaml"
    runs = tmp_path / "runs"
    locks = tmp_path / "locks"
    ledger = tmp_path / "events.jsonl"
    registry.write_text(
        f"""---
status: active
lifecycle: ssot
owner: test
last-reviewed: 2026-06-29
---
version: 1
runner:
  run_state_dir: {runs}
  lock_state_dir: {locks}
  ledger_path: {ledger}
  lock_ttl_hours: 1
workflows:
  - id: mini
    title: Mini
    purpose: Test workflow
    allowed_lanes: [docs]
    lock_scopes: [mini-lock]
    surfaces:
      read: [README.md]
      write: [README.md]
    phases:
      preflight:
        - id: true-preflight
          mode: required
          command: [python, -c, pass]
      execute:
        - id: manual-edit
          mode: manual
          command: [agent, edit]
      verification:
        - id: true-verify
          mode: required
          command: [python, -c, pass]
      closeout:
        - id: true-closeout
          mode: required
          command: [python, -c, pass]
""",
        encoding="utf-8",
    )
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "real run test",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    record = json.loads(start.stdout)
    run_id = record["run_id"]
    assert record["locks"]
    assert ledger.exists()
    assert "agent_workflow_start" in ledger.read_text(encoding="utf-8")

    handoff = _run_workflow("--registry", str(registry), "handoff", run_id)
    assert handoff.returncode == 0, handoff.stderr
    assert f"Agent Workflow Handoff: {run_id}" in handoff.stdout
    assert "real run test" in handoff.stdout

    close = _run_workflow(
        "--registry",
        str(registry),
        "close",
        run_id,
        "--status",
        "ok",
        "--evidence",
        "pytest mini",
        "--json",
    )
    assert close.returncode == 0, close.stderr
    closed = json.loads(close.stdout)
    assert closed["released_locks"]
    assert not list(locks.glob("*.lock.yaml"))
    ledger_text = ledger.read_text(encoding="utf-8")
    assert "agent_workflow_close" in ledger_text
    assert "pytest mini" in ledger_text


def test_change_lane_knows_agent_workflow_files() -> None:
    module = _load_module_from_source(LANE_MODULE_PATH, "change_lane_check")

    assert module.classify("bin/agent-workflow.py", set()) == "governance_code"
    assert module.classify(".omo/_truth/registry/agent-workflows.yaml", set()) == "governance_code"
    assert module.classify(".agents/skills/project-governance/SKILL.md", set()) == "governance_code"
