from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_MODULE_PATH = ROOT / "bin" / "agent-workflow.py"
LANE_MODULE_PATH = ROOT / "bin" / "change-lane-check.py"
LAYER_INDEX_SCRIPT = ROOT / "bin" / "project-layer-index.py"
DOC_SSOT_SCRIPT = ROOT / "bin" / "doc-ssot-lint.py"


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


def _run_layer_index(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(LAYER_INDEX_SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_doc_ssot(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(DOC_SSOT_SCRIPT), *args],
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
    assert "root-agent-workflow-agents" in check_ids
    assert "root-agent-workflow-adapters" in check_ids
    assert "root-agent-workflow-integrations" in check_ids
    assert "root-agent-workflow-observe" in check_ids
    assert "cockpit-agent-workflow-list" in check_ids
    assert "cockpit-agent-workflow-agents" in check_ids
    assert "omo-bridge-help" in check_ids
    assert "mof-capabilities-registry" in check_ids
    assert "mof-schema-validate" in check_ids
    assert "mof-state-bridge" in check_ids
    assert "mof-drift" in check_ids

    adapters = {item["name"]: item for item in report["adapters"]}
    assert adapters["superpowers"]["health"]["ok"] is True
    assert adapters["superpowers"]["health_required"] is True
    assert adapters["superpowers"]["authority"] == "discipline_layer"
    assert adapters["bmad"]["ingress_workflow"] == "c2g-spec-ingress"
    assert adapters["beads"]["ssot_rule"]
    assert adapters["gstack"]["degrade_to"]
    assert "health" in adapters["bmad"]
    assert "health" in adapters["openspec"]
    assert "health" in adapters["beads"]
    assert "health" in adapters["gstack"]

    integrations = {item["name"]: item for item in report["integrations"]}
    assert integrations["gac"]["authority"] == "governance_gate"
    assert integrations["omo"]["health"]["ok"] is True
    assert integrations["c2g"]["health_required"] is True
    assert integrations["mof"]["ssot_rule"]


def test_agent_workflow_lists_mof_and_external_adapter_workflows() -> None:
    result = _run_workflow("list", "--json")

    assert result.returncode == 0, result.stderr
    workflow_ids = {item["id"] for item in json.loads(result.stdout)}
    assert "mof-model-change" in workflow_ids
    assert "mof-state-bridge-audit" in workflow_ids
    assert "external-adapter-sync" in workflow_ids


def test_agent_workflow_lists_external_adapter_contracts() -> None:
    result = _run_workflow("adapters", "--json")

    assert result.returncode == 0, result.stderr
    adapters = {item["name"]: item for item in json.loads(result.stdout)}
    assert adapters["bmad"]["authority"] == "input_adapter"
    assert adapters["openspec"]["ingress_workflow"] == "c2g-spec-ingress"
    assert adapters["gstack"]["authority"] == "memory_adapter"
    assert adapters["superpowers"]["skill"] == "using-superpowers"


def test_agent_workflow_lists_internal_integration_contracts() -> None:
    result = _run_workflow("integrations", "--json")

    assert result.returncode == 0, result.stderr
    integrations = {item["name"]: item for item in json.loads(result.stdout)}
    assert integrations["gac"]["authority"] == "governance_gate"
    assert integrations["omo"]["authority"] == "state_broker"
    assert integrations["cockpit"]["authority"] == "entrypoint"
    assert integrations["mof"]["health_required"] is True


def test_agent_workflow_bootstrap_is_single_startup_entrypoint() -> None:
    result = _run_workflow("bootstrap", "--skip-health", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["lint"]["ok"] is True
    assert report["health"] is None
    assert {item["id"] for item in report["workflows"]}
    assert {item["id"] for item in report["agent_profiles"]}
    assert {item["name"] for item in report["integrations"]}
    assert {item["name"] for item in report["adapters"]}
    assert "start" in report["next_commands"]


def test_project_layer_index_digest_is_fresh() -> None:
    result = _run_layer_index("--check")

    assert result.returncode == 0, result.stderr
    assert "project-layer-index.md" in result.stdout


def test_doc_ssot_semantic_contracts_pass() -> None:
    result = _run_doc_ssot("--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True


def test_agent_profiles_are_queryable() -> None:
    result = _run_workflow("agents", "--json")

    assert result.returncode == 0, result.stderr
    profiles = {item["id"]: item for item in json.loads(result.stdout)}
    assert "governance-agent" in profiles
    assert "observer-agent" in profiles
    assert "mof-agent" in profiles
    assert "adapter-agent" in profiles
    assert "observer-audit" in profiles["observer-agent"]["allowed_workflows"]
    assert "mof-state-bridge-audit" in profiles["observer-agent"]["allowed_workflows"]
    assert "mof-model-change" in profiles["mof-agent"]["allowed_workflows"]
    assert "external-adapter-sync" in profiles["adapter-agent"]["allowed_workflows"]


def test_agent_profile_lint_rejects_unknown_workflow_role(tmp_path: Path) -> None:
    registry = tmp_path / "agent-workflows.yaml"
    registry.write_text(
        """---
status: active
lifecycle: ssot
owner: test
last-reviewed: 2026-06-29
---
version: 1
agent_profiles:
  docs-agent:
    purpose: Docs
    allowed_workflows: [mini]
    can_write_lanes: [docs]
workflows:
  - id: mini
    title: Mini
    purpose: Test workflow
    agents:
      roles: [missing-agent]
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

    result = _run_workflow("--registry", str(registry), "lint", "--json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert "mini: unknown agent role: missing-agent" in report["errors"]


def test_lint_rejects_adapter_without_ssot_contract(tmp_path: Path) -> None:
    registry = tmp_path / "agent-workflows.yaml"
    registry.write_text(
        """---
status: active
lifecycle: ssot
owner: test
last-reviewed: 2026-06-29
---
version: 1
external_patterns:
  loose-tool:
    status: optional_adapter
    command: loose-tool
    pattern: unmanaged tool
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

    result = _run_workflow("--registry", str(registry), "lint", "--json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert "external_patterns.loose-tool: missing authority" in report["errors"]
    assert "external_patterns.loose-tool: missing ssot_rule" in report["errors"]
    assert "external_patterns.loose-tool: missing ingress_workflow" in report["errors"]


def test_lint_rejects_internal_integration_without_contract(tmp_path: Path) -> None:
    registry = tmp_path / "agent-workflows.yaml"
    registry.write_text(
        """---
status: active
lifecycle: ssot
owner: test
last-reviewed: 2026-06-29
---
version: 1
internal_integrations:
  loose-integration:
    health_command: [python, -c, pass]
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

    result = _run_workflow("--registry", str(registry), "lint", "--json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert "internal_integrations.loose-integration: missing status" in report["errors"]
    assert "internal_integrations.loose-integration: missing authority" in report["errors"]
    assert "internal_integrations.loose-integration: missing owner" in report["errors"]
    assert "internal_integrations.loose-integration: missing ssot_rule" in report["errors"]


def test_start_run_dry_run_does_not_write_state() -> None:
    run_dir = ROOT / ".omo" / "_delivery" / "agent-workflows" / "runs"
    before = set(run_dir.glob("*.yaml")) if run_dir.exists() else set()
    result = _run_workflow(
        "start",
        "project-doc-change",
        "--actor",
        "test",
        "--profile",
        "docs-agent",
        "--objective",
        "dry-run test",
        "--dry-run",
        "--json",
    )
    after = set(run_dir.glob("*.yaml")) if run_dir.exists() else set()

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["status"] == "active"
    assert record["agent_profile"] == "docs-agent"
    assert record["locks"] == []
    assert before == after


def test_start_run_requires_profile_for_governed_workflow() -> None:
    result = _run_workflow(
        "start",
        "project-doc-change",
        "--actor",
        "test",
        "--objective",
        "missing profile test",
        "--dry-run",
        "--json",
    )

    assert result.returncode == 2
    assert "project-doc-change requires --profile" in result.stderr


def test_start_run_rejects_profile_outside_workflow_roles() -> None:
    result = _run_workflow(
        "start",
        "project-code-change",
        "--project",
        "omo",
        "--actor",
        "test",
        "--profile",
        "docs-agent",
        "--objective",
        "wrong profile test",
        "--dry-run",
        "--json",
    )

    assert result.returncode == 2
    assert "agent profile docs-agent cannot run workflow project-code-change" in result.stderr


def test_run_execute_requires_profile_for_governed_workflow() -> None:
    result = _run_workflow(
        "run",
        "project-doc-change",
        "--stage",
        "preflight",
        "--execute",
        "--json",
    )

    assert result.returncode == 2
    assert "project-doc-change requires --profile" in result.stderr


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

    observe = _run_workflow("--registry", str(registry), "observe", "--json")
    assert observe.returncode == 0, observe.stderr
    observed = json.loads(observe.stdout)
    assert observed["decision"] == "continue"
    assert observed["findings"] == []


def test_observe_flags_orphan_lock(tmp_path: Path) -> None:
    registry = tmp_path / "agent-workflows.yaml"
    locks = tmp_path / "locks"
    registry.write_text(
        f"""---
status: active
lifecycle: ssot
owner: test
last-reviewed: 2026-06-29
---
version: 1
runner:
  run_state_dir: {tmp_path / "runs"}
  lock_state_dir: {locks}
  ledger_path: {tmp_path / "events.jsonl"}
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
    locks.mkdir()
    (locks / "orphan.lock.yaml").write_text(
        "run_id: missing-run\nscope: mini-lock\nexpires_at: 2020-01-01T00:00:00Z\n",
        encoding="utf-8",
    )

    observe = _run_workflow("--registry", str(registry), "observe", "--json")

    assert observe.returncode == 1
    report = json.loads(observe.stdout)
    assert report["decision"] == "halt"
    assert report["findings"][0]["kind"] == "orphan_lock"


def test_change_lane_knows_agent_workflow_files() -> None:
    module = _load_module_from_source(LANE_MODULE_PATH, "change_lane_check")

    assert module.classify("bin/agent-workflow.py", set()) == "governance_code"
    assert module.classify("bin/project-layer-index.py", set()) == "governance_code"
    assert module.classify(".omo/_truth/registry/agent-workflows.yaml", set()) == "governance_code"
    assert module.classify(".agents/skills/project-governance/SKILL.md", set()) == "governance_code"
    assert module.classify("docs/generated/project-layer-index.md", set()) == "docs"
