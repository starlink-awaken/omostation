from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_MODULE_PATH = ROOT / "bin" / "agent-workflow.py"
LANE_MODULE_PATH = ROOT / "bin" / "change-lane-check.py"
GAC_GATE_MODULE_PATH = ROOT / "bin" / "gac" / "gac-local-gate.py"
LAYER_INDEX_SCRIPT = ROOT / "bin" / "mof" / "project-layer-index.py"
DOC_SSOT_SCRIPT = ROOT / "bin" / "ssot" / "doc-ssot-lint.py"
AFFECTED_GRAPH_SCRIPT = ROOT / "bin" / "gac" / "affected-graph.py"
_CREATED_RECEIPTS: list[Path] = []


def _sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _requirements_digest(requirements: list[dict[str, str]]) -> str:
    canonical = json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_ref(canonical.encode("utf-8"))


@pytest.fixture(scope="session", autouse=True)
def _cleanup_affected_graph_receipts():
    yield
    for receipt in _CREATED_RECEIPTS:
        receipt.unlink(missing_ok=True)


def _load_module_from_source(path: Path, name: str):
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__dict__["__file__"] = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _load_root_workflow_wrapper():
    return _load_module_from_source(WORKFLOW_MODULE_PATH, f"agent_workflow_wrapper_{uuid.uuid4().hex}")


def _write_bet_workspace(
    workspace: Path,
    *,
    bet_id: str = "BET-TEST-SPINE",
    status: str = "candidate",
    write_surfaces: list[str] | None = None,
    capability_requirements: list[dict[str, str]] | None = None,
) -> tuple[str, Path]:
    relative_spec = "docs/superpowers/specs/test-spine.md"
    spec_path = workspace / relative_spec
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "---\n"
        "schema_version: specification/v1\n"
        "spec_version: 1.0.0\n"
        "status: accepted\n"
        f"bet_id: {bet_id}\n"
        "---\n\n"
        "# Frozen specification\n",
        encoding="utf-8",
    )
    # Instruction pack file is required by resolve_instruction_binding when
    # compiling WorkPacket v2; mirror the repo layout so tmp workspaces work.
    instruction_path = workspace / "docs/operations/blueprint-agent-instruction-pack-v1.md"
    instruction_path.parent.mkdir(parents=True, exist_ok=True)
    instruction_path.write_text("# Blueprint Agent Instruction Pack\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    ledger_path = workspace / "docs/plans/3y-bet-ledger.yaml"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    surfaces_yaml = "".join(
        f"      - {surface}\n" for surface in (write_surfaces or ["bin/agent-workflow.py", "tests/**"])
    )
    capability_yaml = ""
    if capability_requirements is not None:
        if capability_requirements:
            capability_yaml = "    capability_requirements:\n" + "".join(
                "      - capability_id: {capability_id}\n"
                "        operation: {operation}\n"
                "        effect: {effect}\n".format(**item)
                for item in capability_requirements
            )
        else:
            capability_yaml = "    capability_requirements: []\n"
    ledger_path.write_text(
        f"""bets:
  - id: {bet_id}
    status: {status}
    track: T1-TRUTH
    window: Y1Q3
    title: Spec binding spine
    appetite: 1 day
    priority: P0
    risk_level: L2
    human_gate: true
    goal: Bind accepted specification to one packet identity
    non_goals: [No second ledger]
    done_when: [Canonical binding is enforced]
    verify:
      - cmd: python3 -c pass
        expect: exit 0
    workflow: bet-execution
    write_surfaces:
{surfaces_yaml}{capability_yaml}    accepted_specifications:
      - spec_ref: repo://{relative_spec}
        spec_version: 1.0.0
        content_digest: sha256:{digest}
        decision_ref: decision://accepted/{bet_id}
""",
        encoding="utf-8",
    )
    return bet_id, spec_path


@pytest.fixture(scope="session")
def _bet_workflow_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Provide a startable ledger without depending on live BET lifecycle state."""
    workspace = tmp_path_factory.mktemp("bet-workflow-workspace")
    shutil.copytree(ROOT / "projects/omo/src/omo", workspace / "projects/omo/src/omo")
    ecos_package = workspace / "projects/ecos/src/ecos"
    ecos_package.parent.mkdir(parents=True, exist_ok=True)
    ecos_package.symlink_to(ROOT / "projects/ecos/src/ecos", target_is_directory=True)
    plan_dir = workspace / "bin/plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORKFLOW_MODULE_PATH, workspace / "bin/agent-workflow.py")
    shutil.copy2(ROOT / "bin/plan/bet-ledger.py", plan_dir / "bet-ledger.py")
    shutil.copy2(ROOT / "bin/plan/chain_bind.py", plan_dir / "chain_bind.py")
    shutil.copy2(ROOT / "bin/capability-sync.py", workspace / "bin/capability-sync.py")
    lib_dir = workspace / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "capability_native_inspection.py",
        "capability_native_receipt.py",
        "capability_native_sources.py",
        "capability_sync_verification_helpers.py",
        "capability_trace_binding.py",
    ):
        shutil.copy2(ROOT / "lib" / name, lib_dir / name)
    shutil.copytree(
        ROOT / ".omo/_truth/registry/agent-workflows",
        workspace / ".omo/_truth/registry/agent-workflows",
    )
    identity_path = workspace / ".git" / "agent-clone-identity.json"
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(
        json.dumps(
            {
                "schema": "agent-clone-identity/v2",
                "ready": True,
                "agent_id": "test-agent",
                "actor_id": "test-agent",
                "delivery_attempt_id": "attempt-test",
                "canonical_root": str(workspace.resolve()),
                "working_branch": "agent/test-agent--attempt-test",
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".git/HEAD").write_text(
        "ref: refs/heads/agent/test-agent--attempt-test\n",
        encoding="utf-8",
    )
    _write_bet_workspace(workspace, bet_id="BET-Y1Q3-T4-01")
    return workspace


def _run_workflow(*args: str) -> subprocess.CompletedProcess[str]:
    # 清 VIRTUAL_ENV: CI 里 interface-check 先 cd projects/omo + uv sync 会
    # 残留 VIRTUAL_ENV=projects/omo/.venv, uv run 在根仓跑时告警 → 断言失败.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.setdefault("AGCP_REQUIREMENT_ITERATION_GATE", "0")
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(WORKFLOW_MODULE_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _run_root_workflow_strict(
    *args: str,
    workspace: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["AGCP_REQUIREMENT_ITERATION_GATE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(workspace / "bin/agent-workflow.py"), *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _run_direct_omo_workflow(
    *args: str,
    workspace: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(workspace / "projects/omo/src"),
            str(ROOT / "projects/ecos/src"),
            env.get("PYTHONPATH", ""),
        ]
    )
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(ROOT / "projects/omo"),
            "python",
            "-m",
            "omo.workflow.cli",
            *args,
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _isolated_workflow_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "registry"
    shutil.copytree(ROOT / ".omo/_truth/registry/agent-workflows", registry)
    root = registry / "_root.yaml"
    text = root.read_text(encoding="utf-8")
    text = (
        text.replace(
            "run_state_dir: .omo/_delivery/agent-workflows/runs",
            f"run_state_dir: {tmp_path / 'runs'}",
        )
        .replace(
            "lock_state_dir: .omo/_delivery/agent-workflows/locks",
            f"lock_state_dir: {tmp_path / 'locks'}",
        )
        .replace(
            "ledger_path: .omo/_delivery/agent-workflows/events.jsonl",
            f"ledger_path: {tmp_path / 'events.jsonl'}",
        )
    )
    root.write_text(text, encoding="utf-8")
    return registry


def _snapshot_workflow_state(tmp_path: Path) -> dict[str, bytes]:
    return {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }


def _write_affected_receipt(tmp_path: Path, *changed_projects: str, name: str = "affected-receipt.json") -> Path:
    del tmp_path, name
    receipt_ref = Path(".omo/evidence") / f"pytest-affected-{uuid.uuid4().hex}.json"
    output = ROOT / receipt_ref
    result = subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(AFFECTED_GRAPH_SCRIPT),
            "--workspace-root",
            str(ROOT),
            "--changed-projects",
            *changed_projects,
            "--output",
            str(receipt_ref),
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    _CREATED_RECEIPTS.append(output)
    return receipt_ref


def _run_layer_index(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.setdefault("AGCP_REQUIREMENT_ITERATION_GATE", "0")
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(LAYER_INDEX_SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _run_doc_ssot(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.setdefault("AGCP_REQUIREMENT_ITERATION_GATE", "0")
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(DOC_SSOT_SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _write_control_plane_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "agent-workflows.yaml"
    runs = tmp_path / "runs"
    locks = tmp_path / "locks"
    ledger = tmp_path / "events.jsonl"
    registry.write_text(
        f"""---
status: active
lifecycle: ssot
owner: test
last-reviewed: 2026-06-30
---
version: 1
runner:
  workspace_root: {tmp_path}
  run_state_dir: {runs}
  lock_state_dir: {locks}
  ledger_path: {ledger}
  lock_ttl_hours: 1
claim_policy:
  mode: advisory
  required_paths: [README.md]
diff_checks:
  - id: readme-check
    description: README check
    required: true
    paths: [README.md]
    command: [python3, -c, pass]
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
          command: [python3, -c, pass]
      execute:
        - id: manual-edit
          mode: manual
          command: [agent, edit]
      verification:
        - id: true-verify
          mode: required
          command: [python3, -c, pass]
      closeout:
        - id: true-closeout
          mode: required
          command: [python3, -c, pass]
""",
        encoding="utf-8",
    )
    return registry


def test_prepare_bet_execution_builds_recomputable_ecos_packet_identity(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)

    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)

    packet = prepared["work_packet"]
    assert packet["schema_version"] == "work-packet/v2"
    assert packet["bet_id"] == bet_id
    assert packet["spec_binding"]["decision_ref"] == f"decision://accepted/{bet_id}"
    assert packet["instruction_binding"] == prepared["instruction_binding"]
    assert prepared["instruction_binding"]["instruction_ref"] == (
        "repo://docs/operations/blueprint-agent-instruction-pack-v1.md"
    )
    assert prepared["instruction_binding"]["instruction_profile"] == "executor"
    assert prepared["instruction_binding"]["content_digest"].startswith("sha256:")
    assert packet["scope"]["write_surfaces"] == ["bin/agent-workflow.py", "tests/**"]
    assert "docs/operations/blueprint-agent-instruction-pack-v1.md" in packet["scope"]["read_surfaces"]
    assert prepared["work_packet_hash"].startswith("sha256:")


def test_prepare_bet_execution_digests_declared_empty_requirements(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path, capability_requirements=[])

    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)

    assert prepared["work_packet"]["capability_requirements"] == []
    assert prepared["capability_requirements_digest"].startswith("sha256:")


def test_work_packet_compiles_capability_requirements_and_preserves_absent_vs_empty() -> None:
    module = _load_root_workflow_wrapper()
    ledger = module._load_bet_ledger_module()
    binding = {
        "spec_ref": "repo://docs/superpowers/specs/test-spine.md",
        "spec_version": "1.0.0",
        "content_digest": "sha256:" + "a" * 64,
        "decision_ref": "decision://accepted/BET-TEST-SPINE",
    }
    instruction = {
        "instruction_ref": "repo://docs/operations/blueprint-agent-instruction-pack-v1.md",
        "instruction_version": "blueprint-agent-instruction-pack/v1",
        "content_digest": "sha256:" + "b" * 64,
        "instruction_profile": "executor",
    }
    requirements = [
        {"capability_id": "skill:git-discipline", "operation": "load", "effect": "read_only"},
        {"capability_id": "workflow:bet-execution", "operation": "load", "effect": "read_only"},
    ]

    absent = ledger._work_packet_from_bet({"id": "BET-TEST-SPINE"}, binding, instruction)
    empty = ledger._work_packet_from_bet({"id": "BET-TEST-SPINE", "capability_requirements": []}, binding, instruction)
    present = ledger._work_packet_from_bet(
        {"id": "BET-TEST-SPINE", "capability_requirements": requirements}, binding, instruction
    )

    assert "capability_requirements" not in absent
    assert empty["capability_requirements"] == []
    assert present["capability_requirements"] == requirements


def _set_capability_requirements(workspace: Path, requirements: list[dict[str, str]]) -> None:
    ledger_path = workspace / "docs/plans/3y-bet-ledger.yaml"
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    ledger["bets"][0]["capability_requirements"] = requirements
    ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    identity_path = workspace / ".git/agent-clone-identity.json"
    if identity_path.exists():
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["canonical_root"] = str(workspace.resolve())
        identity_path.write_text(json.dumps(identity), encoding="utf-8")


def _capability_requirements() -> list[dict[str, str]]:
    return [{"capability_id": "workflow:bet-execution", "operation": "load", "effect": "read_only"}]


def test_root_start_preflight_accepts_native_requirement_and_persists_redacted_receipt(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(_bet_workflow_workspace, workspace, symlinks=True)
    _set_capability_requirements(workspace, _capability_requirements())
    registry = _isolated_workflow_registry(tmp_path)

    result = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--dry-run",
        "--json",
        workspace=workspace,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["capability_requirements_digest"].startswith("sha256:")
    preflight = record["capability_preflight"]
    assert preflight["invoked"] is False
    assert preflight["value_indicator_policy"] is False
    receipt = preflight["receipts"][0]
    assert receipt["capability_id"] == "workflow:bet-execution"
    assert receipt["source_digest"] == _sha256_ref(
        (workspace / ".omo/_truth/registry/agent-workflows/workflows/bet-execution.yaml").read_bytes()
    )
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["source_digest"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["receipt_digest"])
    assert set(preflight["binding"]) == {
        "correlation_id",
        "workflow_run_id",
        "packet_id",
        "packet_hash",
        "assignment_id",
        "dispatch_id",
        "actor_id",
        "delivery_attempt_id",
    }
    assert preflight["binding"]["correlation_id"] == record["run_id"]


def _write_mcp_preflight_workspace(root: Path) -> dict[str, Any]:
    identity_path = root / ".git/agent-clone-identity.json"
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(
        json.dumps(
            {
                "schema": "agent-clone-identity/v2",
                "ready": True,
                "agent_id": "test-actor",
                "actor_id": "test-actor",
                "delivery_attempt_id": "test-attempt",
                "canonical_root": str(root.resolve()),
                "working_branch": "agent/test-actor--test-attempt",
            }
        ),
        encoding="utf-8",
    )
    (root / ".git/HEAD").write_text(
        "ref: refs/heads/agent/test-actor--test-attempt\n",
        encoding="utf-8",
    )
    source = root / "native/demo_mcp.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "from fastmcp import FastMCP\n"
        "mcp = FastMCP('demo')\n"
        "@mcp.tool()\n"
        "async def inspect_item(value: str) -> str:\n"
        "    return value\n",
        encoding="utf-8",
    )
    registry_path = root / "docs/generated/capability-registry.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0.0",
                "schema": "capability-registry/v1",
                "owner": "workspace-capability-governance",
                "writer": "bin/ssot/gen-capability-registry.py",
                "mcp_servers": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "file": "native/demo_mcp.py",
                        "exists": True,
                        "tools": ["inspect_item"],
                    }
                ],
                "bos_services": {"domains": {}},
                "cli_commands": [],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    requirement = {
        "capability_id": "mcp-server:demo",
        "operation": "load",
        "effect": "read_only",
    }
    return {
        "work_packet": {
            "packet_id": "WP-BET-TEST",
            "capability_requirements": [requirement],
        },
        "work_packet_hash": "sha256:" + "a" * 64,
        "capability_requirements_digest": _requirements_digest([requirement]),
    }


def test_root_preflight_resolves_and_inspects_exact_mcp_projection(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    delivery_identity = _write_mcp_preflight_workspace(tmp_path)

    preflight = module._capability_preflight(delivery_identity, "run-mcp", workspace=tmp_path)

    receipt = preflight["receipts"][0]
    assert receipt["capability_id"] == "mcp-server:demo"
    assert receipt["source_digest"] == _sha256_ref((tmp_path / "native/demo_mcp.py").read_bytes())
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["source_digest"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["receipt_digest"])
    assert preflight["invoked"] is False
    assert preflight["value_indicator_policy"] is False


def test_root_preflight_rejects_projection_read_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_root_workflow_wrapper()
    delivery_identity = _write_mcp_preflight_workspace(tmp_path)
    capability_sync = module._load_capability_sync_module()
    original = capability_sync.load_registry

    def racing_load(path: Path) -> dict[str, Any]:
        registry = original(path)
        path.write_text(path.read_text(encoding="utf-8") + "# raced\n", encoding="utf-8")
        return registry

    monkeypatch.setattr(capability_sync, "load_registry", racing_load)

    with pytest.raises(module.WorkflowError, match="CAPABILITY_PREFLIGHT_SOURCE_REJECTED"):
        module._capability_preflight(delivery_identity, "run-race", workspace=tmp_path)


def test_root_preflight_rejects_tampered_requirements_digest_before_clone_reads(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    delivery_identity = _write_mcp_preflight_workspace(tmp_path)
    delivery_identity["capability_requirements_digest"] = "sha256:" + "0" * 64
    (tmp_path / ".git/agent-clone-identity.json").unlink()

    with pytest.raises(module.WorkflowError, match="CAPABILITY_PREFLIGHT_REQUIREMENTS_DIGEST_MISMATCH"):
        module._capability_preflight(delivery_identity, "run-tampered", workspace=tmp_path)


@pytest.mark.parametrize(
    "identity_mode",
    ["copied", "wrong-root", "wrong-agent", "wrong-branch", "wrong-live-branch"],
)
def test_root_preflight_rejects_mismatched_v2_clone_identity(
    tmp_path: Path, identity_mode: str
) -> None:
    module = _load_root_workflow_wrapper()
    delivery_identity = _write_mcp_preflight_workspace(tmp_path)
    identity_path = tmp_path / ".git/agent-clone-identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity_mode == "copied":
        identity["canonical_root"] = str(tmp_path / "copied-clone")
    elif identity_mode == "wrong-root":
        identity["canonical_root"] = str(tmp_path.parent.resolve())
    elif identity_mode == "wrong-agent":
        identity["agent_id"] = "different-agent"
    elif identity_mode == "wrong-branch":
        identity["working_branch"] = "agent/test-actor--different-attempt"
    else:
        (tmp_path / ".git/HEAD").write_text(
            "ref: refs/heads/agent/test-actor--different-attempt\n",
            encoding="utf-8",
        )
    identity_path.write_text(json.dumps(identity), encoding="utf-8")

    with pytest.raises(module.WorkflowError, match="CAPABILITY_PREFLIGHT_CLONE_IDENTITY_INVALID"):
        module._capability_preflight(delivery_identity, f"run-{identity_mode}", workspace=tmp_path)


def test_root_preflight_rejects_projection_receipt_drift_with_unchanged_native_source(
    tmp_path: Path,
) -> None:
    module = _load_root_workflow_wrapper()
    delivery_identity = _write_mcp_preflight_workspace(tmp_path)
    initial = module._capability_preflight(delivery_identity, "run-projection", workspace=tmp_path)
    registry_path = tmp_path / "docs/generated/capability-registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry["mcp_servers"][0]["name"] = "Projection metadata changed"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=True), encoding="utf-8")

    with pytest.raises(module.WorkflowError, match="CAPABILITY_PREFLIGHT_SOURCE_DRIFT"):
        module._capability_preflight(
            delivery_identity,
            "run-projection",
            workspace=tmp_path,
            expected_preflight=initial,
        )


def test_root_preflight_rebinds_projected_receipt_when_only_packet_hash_changes(
    tmp_path: Path,
) -> None:
    module = _load_root_workflow_wrapper()
    original_identity = _write_mcp_preflight_workspace(tmp_path)
    initial = module._capability_preflight(original_identity, "run-rebind", workspace=tmp_path)
    refreshed_identity = copy.deepcopy(original_identity)
    refreshed_identity["work_packet_hash"] = "sha256:" + "c" * 64

    refreshed = module._capability_preflight(
        refreshed_identity,
        "run-rebind",
        workspace=tmp_path,
        expected_preflight=initial,
    )

    assert refreshed["binding"]["packet_hash"] == refreshed_identity["work_packet_hash"]
    assert refreshed["receipts"][0]["source_digest"] == initial["receipts"][0]["source_digest"]
    assert refreshed["receipts"][0]["receipt_digest"] != initial["receipts"][0]["receipt_digest"]


def test_root_start_without_capability_requirements_skips_preflight_and_clone_identity(
    tmp_path: Path, _bet_workflow_workspace: Path
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(_bet_workflow_workspace, workspace, symlinks=True)
    (workspace / ".git/agent-clone-identity.json").unlink()
    registry = _isolated_workflow_registry(tmp_path)

    result = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--dry-run",
        "--json",
        workspace=workspace,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert "capability_requirements_digest" not in record
    assert "capability_preflight" not in record


@pytest.mark.parametrize("identity_mode", ["missing", "invalid"])
def test_root_start_preflight_rejects_clone_identity_before_any_mutation(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
    identity_mode: str,
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(_bet_workflow_workspace, workspace, symlinks=True)
    _set_capability_requirements(workspace, _capability_requirements())
    identity = workspace / ".git/agent-clone-identity.json"
    if identity_mode == "missing":
        identity.unlink()
    else:
        identity.write_text(json.dumps({"schema": "agent-clone-identity/v1"}), encoding="utf-8")
    registry = _isolated_workflow_registry(tmp_path)
    before = _snapshot_workflow_state(tmp_path)

    result = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=workspace,
    )

    assert result.returncode == 2
    assert "CAPABILITY_PREFLIGHT" in result.stderr
    assert _snapshot_workflow_state(tmp_path) == before


def test_root_start_preflight_rejects_missing_source_before_any_mutation(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(_bet_workflow_workspace, workspace, symlinks=True)
    _set_capability_requirements(
        workspace,
        [{"capability_id": "workflow:not-installed", "operation": "load", "effect": "read_only"}],
    )
    registry = _isolated_workflow_registry(tmp_path)
    before = _snapshot_workflow_state(tmp_path)

    result = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=workspace,
    )

    assert result.returncode == 2
    assert "CAPABILITY_PREFLIGHT" in result.stderr
    assert list((tmp_path / "runs").glob("*.yaml")) == []
    assert _snapshot_workflow_state(tmp_path) == before


def test_root_parent_child_preserves_exact_capability_identity(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(_bet_workflow_workspace, workspace, symlinks=True)
    _set_capability_requirements(workspace, _capability_requirements())
    registry = _isolated_workflow_registry(tmp_path)
    parent_result = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=workspace,
    )
    assert parent_result.returncode == 0, parent_result.stderr
    parent = json.loads(parent_result.stdout)

    child_result = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--parent-run",
        parent["run_id"],
        "--dry-run",
        "--json",
        workspace=workspace,
    )
    assert child_result.returncode == 0, child_result.stderr
    child = json.loads(child_result.stdout)
    for key in ("capability_requirements_digest", "capability_preflight"):
        assert child[key] == parent[key]


def test_refresh_updates_preflight_atomically_and_rejects_capability_source_drift(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    requirement = [{"capability_id": "skill:test-capability", "operation": "load", "effect": "read_only"}]
    registry, run_id, _before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
        capability_requirements=requirement,
    )
    _write_bet_workspace(
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "bin/gac/test_agent_clone.py", "tests/**"],
        capability_requirements=requirement,
    )

    _initial_path, initial = module._wf_life.read_run(registry, run_id)
    initial_source_digest = initial["capability_preflight"]["receipts"][0]["source_digest"]
    result = module._refresh_packet_run(registry, run_id, workspace=tmp_path, authoritative_ref=None)
    _path, refreshed = module._wf_life.read_run(registry, run_id)
    assert result["reason"] == "work_packet_refreshed"
    assert refreshed["capability_preflight"]["binding"]["packet_hash"] == refreshed["work_packet_hash"]
    assert refreshed["capability_preflight"]["receipts"][0]["source_digest"] == initial_source_digest

    run_path, _payload = module._wf_life.read_run(registry, run_id)
    before_run = run_path.read_bytes()
    ledger_path = tmp_path / "events.jsonl"
    before_ledger = ledger_path.read_bytes()
    skill_path = tmp_path / ".agents/skills/test-capability/SKILL.md"
    skill_path.write_text(skill_path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    with pytest.raises(module.WorkflowError, match="CAPABILITY_PREFLIGHT_SOURCE_DRIFT"):
        module._refresh_packet_run(registry, run_id, workspace=tmp_path, authoritative_ref=None)
    assert run_path.read_bytes() == before_run
    assert ledger_path.read_bytes() == before_ledger


def test_prepare_bet_execution_rejects_non_startable_status(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path, status="done")

    with pytest.raises(module.WorkflowError, match="BET_STATUS_NOT_STARTABLE"):
        module._prepare_bet_execution(bet_id, workspace=tmp_path)


def test_prepare_bet_execution_rejects_unaccepted_decision(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    ledger = tmp_path / "docs/plans/3y-bet-ledger.yaml"
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace("decision://accepted/", "decision://proposed/"),
        encoding="utf-8",
    )

    with pytest.raises(module.WorkflowError, match="SPEC_DECISION_NOT_ACCEPTED"):
        module._prepare_bet_execution(bet_id, workspace=tmp_path)


def test_prepare_bet_execution_rejects_missing_instruction_pack(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    (tmp_path / "docs/operations/blueprint-agent-instruction-pack-v1.md").unlink()

    with pytest.raises(module.WorkflowError, match="INSTRUCTION_PACK_MISSING"):
        module._prepare_bet_execution(bet_id, workspace=tmp_path)


def test_claim_scope_accepts_exact_directory_and_globbed_paths(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "projects/omo", "tests/**"],
    )
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)
    payload = {"bet_id": bet_id, **prepared}

    module._validate_packet_run(payload, ["bin/agent-workflow.py"], workspace=tmp_path)
    module._validate_packet_run(payload, ["projects/omo/src/omo/example.py"], workspace=tmp_path)
    module._validate_packet_run(payload, ["tests/unit/test_example.py"], workspace=tmp_path)


def test_claim_scope_rejects_path_outside_packet(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)
    payload = {"bet_id": bet_id, **prepared}

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_SCOPE_MISMATCH"):
        module._validate_packet_run(payload, ["docs/unauthorized.md"], workspace=tmp_path)


def test_claim_scope_rejects_unmodeled_governance_surface(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)
    payload = {"bet_id": bet_id, **prepared}

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_SCOPE_MISMATCH"):
        module._validate_packet_run(
            payload,
            [],
            claimed_surfaces=["governance-state"],
            workspace=tmp_path,
        )


def test_claim_revalidates_spec_digest_after_start(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, spec_path = _write_bet_workspace(tmp_path)
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)
    payload = {"bet_id": bet_id, **prepared}
    spec_path.write_text("# Drifted after start\n", encoding="utf-8")

    with pytest.raises(module.WorkflowError, match="SPEC_DIGEST_MISMATCH"):
        module._validate_packet_run(payload, ["bin/agent-workflow.py"], workspace=tmp_path)


def test_claim_revalidates_instruction_digest_after_start(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)
    payload = {"bet_id": bet_id, **prepared}
    instruction_path = tmp_path / "docs/operations/blueprint-agent-instruction-pack-v1.md"
    instruction_path.write_text("# Drifted after start\n", encoding="utf-8")

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_SOURCE_DRIFT"):
        module._validate_packet_run(payload, ["bin/agent-workflow.py"], workspace=tmp_path)


def test_claim_rejects_tampered_packet_hash(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)
    payload = {"bet_id": bet_id, **prepared, "work_packet_hash": "sha256:" + "0" * 64}

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_HASH_MISMATCH"):
        module._validate_packet_run(payload, ["bin/agent-workflow.py"], workspace=tmp_path)


def test_claim_rejects_malformed_packet_as_contract_error(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)
    prepared["work_packet"]["spec_binding"] = {"spec_ref": "repo://invalid"}
    payload = {"bet_id": bet_id, **prepared}

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_INVALID"):
        module._validate_packet_run(payload, ["bin/agent-workflow.py"], workspace=tmp_path)


def _write_refreshable_run(
    module,
    workspace: Path,
    *,
    write_surfaces: list[str],
    claimed_path: str = "bin/agent-workflow.py",
    capability_requirements: list[dict[str, str]] | None = None,
) -> tuple[dict, str, dict]:
    bet_id, _spec_path = _write_bet_workspace(
        workspace,
        write_surfaces=write_surfaces,
        capability_requirements=capability_requirements,
    )
    if capability_requirements is not None:
        skill = workspace / ".agents/skills/test-capability/SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(
            "---\nname: test-capability\nversion: 1\n---\n\n# Test capability\n",
            encoding="utf-8",
        )
        (workspace / "bin").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "bin/capability-sync.py", workspace / "bin/capability-sync.py")
        lib_dir = workspace / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "capability_native_inspection.py",
            "capability_native_receipt.py",
            "capability_native_sources.py",
            "capability_trace_binding.py",
        ):
            shutil.copy2(ROOT / "lib" / name, lib_dir / name)
        identity_path = workspace / ".git" / "agent-clone-identity.json"
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(
            json.dumps(
                {
                    "schema": "agent-clone-identity/v2",
                    "ready": True,
                    "agent_id": "test-agent",
                    "actor_id": "test-agent",
                    "delivery_attempt_id": "attempt-test",
                    "canonical_root": str(workspace.resolve()),
                    "working_branch": "agent/test-agent--attempt-test",
                }
            ),
            encoding="utf-8",
        )
        (workspace / ".git/HEAD").write_text(
            "ref: refs/heads/agent/test-agent--attempt-test\n",
            encoding="utf-8",
        )
    prepared = module._prepare_bet_execution(bet_id, workspace=workspace)
    registry_path = _write_control_plane_registry(workspace)
    registry = module.load_registry(registry_path)
    run_id = "20260821T000000Z-bet-execution-refresh"
    run_path = workspace / "runs" / f"{run_id}.yaml"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "workflow_id": "bet-execution",
        "status": "active",
        "bet_id": bet_id,
        **prepared,
        "claims": [{"paths": [claimed_path], "surfaces": []}],
    }
    if capability_requirements is not None:
        payload["capability_preflight"] = module._capability_preflight(
            prepared,
            run_id,
            workspace=workspace,
        )
    module._wf_life.write_run(
        run_path,
        payload,
    )
    return registry, run_id, prepared


def _pin_authoritative_main(workspace: Path, message: str) -> str:
    if not (workspace / ".git").exists():
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(
        ["git", "-C", str(workspace), "add", "docs/plans", "docs/operations", "docs/superpowers"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "-c",
            "user.name=Workflow Test",
            "-c",
            "user.email=workflow-test@example.invalid",
            "commit",
            "-qm",
            message,
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(workspace), "update-ref", "refs/remotes/origin/main", revision],
        check=True,
    )
    return revision


def test_refresh_packet_projects_expanded_scope_for_same_accepted_identity(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    _write_bet_workspace(
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "bin/gac/test_agent_clone.py", "tests/**"],
    )

    result = module._refresh_packet_run(
        registry,
        run_id,
        workspace=tmp_path,
        authoritative_ref=None,
    )
    _path, refreshed = module._wf_life.read_run(registry, run_id)

    assert result["reason"] == "work_packet_refreshed"
    assert result["old_work_packet_hash"] == before["work_packet_hash"]
    assert result["work_packet_hash"] != before["work_packet_hash"]
    assert "bin/gac/test_agent_clone.py" in refreshed["work_packet"]["scope"]["write_surfaces"]
    module._validate_packet_run(refreshed, ["bin/gac/test_agent_clone.py"], workspace=tmp_path)


def test_refresh_packet_rejects_scope_shrink_that_orphans_existing_claim(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    _write_bet_workspace(tmp_path, write_surfaces=["tests/**"])

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_SCOPE_MISMATCH"):
        module._refresh_packet_run(
            registry,
            run_id,
            workspace=tmp_path,
            authoritative_ref=None,
        )

    _path, unchanged = module._wf_life.read_run(registry, run_id)
    assert unchanged["work_packet_hash"] == before["work_packet_hash"]


def test_refresh_packet_rejects_instruction_binding_drift(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    instruction = tmp_path / "docs/operations/blueprint-agent-instruction-pack-v1.md"
    instruction.write_text("# Drifted instruction identity\n", encoding="utf-8")

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_REFRESH_INSTRUCTION_DRIFT"):
        module._refresh_packet_run(
            registry,
            run_id,
            workspace=tmp_path,
            authoritative_ref=None,
        )

    _path, unchanged = module._wf_life.read_run(registry, run_id)
    assert unchanged["work_packet_hash"] == before["work_packet_hash"]


def test_refresh_packet_source_alignment_rejects_unmerged_ledger(tmp_path: Path, monkeypatch) -> None:
    module = _load_root_workflow_wrapper()
    bet_id, _spec_path = _write_bet_workspace(tmp_path)
    prepared = module._prepare_bet_execution(bet_id, workspace=tmp_path)

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"different authoritative bytes",
            stderr=b"",
        ),
    )

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_REFRESH_SOURCE_UNMERGED: ledger"):
        module._assert_packet_sources_at_ref(
            tmp_path,
            prepared,
            authoritative_ref="origin/main",
        )


def test_refresh_packet_rejects_malformed_claims_without_changing_packet(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    run_path, payload = module._wf_life.read_run(registry, run_id)
    payload["claims"] = [{"paths": [42], "surfaces": []}]
    module._wf_life.write_run(run_path, payload)

    with pytest.raises(module.WorkflowError, match="WORK_PACKET_REFRESH_CLAIMS_INVALID"):
        module._refresh_packet_run(
            registry,
            run_id,
            workspace=tmp_path,
            authoritative_ref=None,
        )

    _path, unchanged = module._wf_life.read_run(registry, run_id)
    assert unchanged["work_packet_hash"] == before["work_packet_hash"]


def test_refresh_packet_rolls_back_when_audit_append_fails(tmp_path: Path, monkeypatch) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    _write_bet_workspace(
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "bin/gac/test_agent_clone.py", "tests/**"],
    )
    run_path, _payload = module._wf_life.read_run(registry, run_id)
    original_bytes = run_path.read_bytes()
    ledger_path = tmp_path / "events.jsonl"
    original_ledger = ledger_path.read_bytes() if ledger_path.exists() else None

    def fail_append(_registry, _event):
        raise OSError("ledger unavailable")

    monkeypatch.setattr(module._wf_life, "append_ledger_event", fail_append)
    with pytest.raises(module.WorkflowError, match="WORK_PACKET_REFRESH_AUDIT_FAILED"):
        module._refresh_packet_run(
            registry,
            run_id,
            workspace=tmp_path,
            authoritative_ref=None,
        )

    _path, unchanged = module._wf_life.read_run(registry, run_id)
    assert unchanged["work_packet_hash"] == before["work_packet_hash"]
    assert run_path.read_bytes() == original_bytes
    assert (ledger_path.read_bytes() if ledger_path.exists() else None) == original_ledger


def test_refresh_packet_rejects_source_race_without_changing_packet(tmp_path: Path, monkeypatch) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    _write_bet_workspace(
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "bin/gac/test_agent_clone.py", "tests/**"],
    )
    prepare = module._prepare_bet_execution
    calls = 0

    def racing_prepare(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = prepare(*args, **kwargs)
        if calls == 2:
            result = copy.deepcopy(result)
            result["work_packet_hash"] = "sha256:" + "0" * 64
        return result

    monkeypatch.setattr(module, "_prepare_bet_execution", racing_prepare)
    with pytest.raises(module.WorkflowError, match="WORK_PACKET_REFRESH_SOURCE_RACED"):
        module._refresh_packet_run(
            registry,
            run_id,
            workspace=tmp_path,
            authoritative_ref=None,
        )

    _path, unchanged = module._wf_life.read_run(registry, run_id)
    assert unchanged["work_packet_hash"] == before["work_packet_hash"]


def test_refresh_packet_final_alignment_rejects_real_source_change(tmp_path: Path, monkeypatch) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    _write_bet_workspace(
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "bin/gac/test_agent_clone.py", "tests/**"],
    )
    _pin_authoritative_main(tmp_path, "authoritative expanded packet")
    prepare = module._prepare_bet_execution
    calls = 0

    def mutate_after_final_prepare(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = prepare(*args, **kwargs)
        if calls == 2:
            ledger = tmp_path / "docs/plans/3y-bet-ledger.yaml"
            ledger.write_text(ledger.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        return result

    monkeypatch.setattr(module, "_prepare_bet_execution", mutate_after_final_prepare)
    with pytest.raises(module.WorkflowError, match="WORK_PACKET_REFRESH_SOURCE_UNMERGED: ledger"):
        module._refresh_packet_run(registry, run_id, workspace=tmp_path)

    _path, unchanged = module._wf_life.read_run(registry, run_id)
    assert unchanged["work_packet_hash"] == before["work_packet_hash"]


def test_refresh_packet_cli_uses_custom_registry_workspace_root(tmp_path: Path) -> None:
    module = _load_root_workflow_wrapper()
    registry, run_id, before = _write_refreshable_run(
        module,
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "tests/**"],
    )
    _pin_authoritative_main(tmp_path, "initial packet sources")
    _write_bet_workspace(
        tmp_path,
        write_surfaces=["bin/agent-workflow.py", "bin/gac/test_agent_clone.py", "tests/**"],
    )
    authoritative_revision = _pin_authoritative_main(tmp_path, "expand packet scope")

    result = _run_root_workflow_strict(
        "--registry",
        str(tmp_path / "agent-workflows.yaml"),
        "refresh-packet",
        run_id,
        "--json",
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["old_work_packet_hash"] == before["work_packet_hash"]
    assert output["authoritative_revision"] == authoritative_revision
    _path, refreshed = module._wf_life.read_run(registry, run_id)
    assert "bin/gac/test_agent_clone.py" in refreshed["work_packet"]["scope"]["write_surfaces"]


def test_direct_omo_module_start_binds_recomputable_work_packet_v2(
    _bet_workflow_workspace: Path,
) -> None:
    result = _run_direct_omo_workflow(
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--dry-run",
        "--json",
        workspace=_bet_workflow_workspace,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["bet_id"] == "BET-Y1Q3-T4-01"
    assert record["work_packet"]["schema_version"] == "work-packet/v2"
    assert record["work_packet"]["instruction_binding"] == record["instruction_binding"]
    assert record["work_packet_hash"].startswith("sha256:")
    assert record["spec_binding"]["decision_ref"] == "decision://accepted/BET-Y1Q3-T4-01"


def test_direct_omo_module_claim_rejects_path_outside_bound_packet(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=_bet_workflow_workspace,
    )
    assert started.returncode == 0, started.stderr
    run_id = json.loads(started.stdout)["run_id"]

    result = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--path",
        "README.md",
        "--affected-hash",
        str(tmp_path / "not-used.json"),
        workspace=_bet_workflow_workspace,
    )

    assert result.returncode == 2
    assert "WORK_PACKET_SCOPE_MISMATCH" in result.stderr


def test_direct_omo_spawn_inherits_parent_packet_and_rejects_out_of_scope_before_mutation(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=_bet_workflow_workspace,
    )
    assert started.returncode == 0, started.stderr
    parent = json.loads(started.stdout)

    spawned = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "spawn",
        parent["run_id"],
        "observer-audit",
        "--profile",
        "observer-agent",
        "--json",
        workspace=_bet_workflow_workspace,
    )
    assert spawned.returncode == 0, spawned.stderr
    child = json.loads(spawned.stdout)
    for key in ("bet_id", "spec_binding", "work_packet", "work_packet_hash"):
        assert child[key] == parent[key]

    child_path = Path(child["path"])
    before_run = child_path.read_bytes()
    lock_paths = [Path(path) for path in child["locks"]]
    before_locks = {path: path.read_bytes() for path in lock_paths}
    ledger = tmp_path / "events.jsonl"
    before_ledger = ledger.read_bytes()

    claimed = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "claim",
        child["run_id"],
        "--path",
        "README.md",
        "--affected-hash",
        str(tmp_path / "not-created.json"),
        workspace=_bet_workflow_workspace,
    )

    assert claimed.returncode == 2
    assert "WORK_PACKET_SCOPE_MISMATCH" in claimed.stderr
    assert child_path.read_bytes() == before_run
    assert {path: path.read_bytes() for path in lock_paths} == before_locks
    assert ledger.read_bytes() == before_ledger


def test_direct_omo_parent_start_inherits_exact_bound_packet_without_explicit_bet(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=_bet_workflow_workspace,
    )
    assert started.returncode == 0, started.stderr
    parent = json.loads(started.stdout)

    child_start = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--parent-run",
        parent["run_id"],
        "--dry-run",
        "--json",
        workspace=_bet_workflow_workspace,
    )

    assert child_start.returncode == 0, child_start.stderr
    child = json.loads(child_start.stdout)
    for key in ("bet_id", "spec_binding", "work_packet", "work_packet_hash"):
        assert child[key] == parent[key]


def test_root_wrapper_parent_start_inherits_exact_bound_packet_without_explicit_bet(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=_bet_workflow_workspace,
    )
    assert started.returncode == 0, started.stderr
    parent = json.loads(started.stdout)

    child_start = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--parent-run",
        parent["run_id"],
        "--dry-run",
        "--json",
        workspace=_bet_workflow_workspace,
    )

    assert child_start.returncode == 0, child_start.stderr
    child = json.loads(child_start.stdout)
    for key in ("bet_id", "spec_binding", "work_packet", "work_packet_hash"):
        assert child[key] == parent[key]


def test_root_wrapper_parent_start_rejects_conflicting_bet_before_any_mutation(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=_bet_workflow_workspace,
    )
    assert started.returncode == 0, started.stderr
    parent = json.loads(started.stdout)
    before = _snapshot_workflow_state(tmp_path)

    child_start = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--parent-run",
        parent["run_id"],
        "--bet",
        "BET-Y1Q2-T1-14",
        "--json",
        workspace=_bet_workflow_workspace,
    )

    assert child_start.returncode != 0
    assert "WORK_PACKET_PARENT_BET_CONFLICT" in child_start.stderr
    assert _snapshot_workflow_state(tmp_path) == before


def test_root_wrapper_parent_start_rejects_legacy_unbound_parent_before_any_mutation(
    tmp_path: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "observer-audit",
        "--profile",
        "observer-agent",
        "--json",
    )
    assert started.returncode == 0, started.stderr
    parent = json.loads(started.stdout)
    before = _snapshot_workflow_state(tmp_path)

    child_start = _run_root_workflow_strict(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--parent-run",
        parent["run_id"],
        "--json",
    )

    assert child_start.returncode != 0
    assert "WORK_PACKET_PARENT_BINDING_REQUIRED" in child_start.stderr
    assert _snapshot_workflow_state(tmp_path) == before


def test_direct_omo_parent_start_rejects_conflicting_bet_before_any_mutation(
    tmp_path: Path,
    _bet_workflow_workspace: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--json",
        workspace=_bet_workflow_workspace,
    )
    assert started.returncode == 0, started.stderr
    parent = json.loads(started.stdout)
    before = _snapshot_workflow_state(tmp_path)

    child_start = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "start",
        "bet-execution",
        "--profile",
        "governance-agent",
        "--parent-run",
        parent["run_id"],
        "--bet",
        "BET-Y1Q2-T1-14",
        "--json",
        workspace=_bet_workflow_workspace,
    )

    assert child_start.returncode == 2
    assert "WORK_PACKET_PARENT_BET_CONFLICT" in child_start.stderr
    assert _snapshot_workflow_state(tmp_path) == before


def test_direct_omo_spawn_rejects_legacy_unbound_parent_before_any_mutation(
    tmp_path: Path,
) -> None:
    registry = _isolated_workflow_registry(tmp_path)
    started = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "start",
        "observer-audit",
        "--profile",
        "observer-agent",
        "--json",
    )
    assert started.returncode == 0, started.stderr
    parent = json.loads(started.stdout)
    before = _snapshot_workflow_state(tmp_path)

    spawned = _run_direct_omo_workflow(
        "--registry",
        str(registry),
        "spawn",
        parent["run_id"],
        "observer-audit",
        "--profile",
        "observer-agent",
        "--json",
    )

    assert spawned.returncode == 2
    assert "WORK_PACKET_PARENT_BINDING_REQUIRED" in spawned.stderr
    assert _snapshot_workflow_state(tmp_path) == before


def test_legacy_readonly_workflow_start_remains_compatible() -> None:
    result = _run_workflow(
        "start",
        "observer-audit",
        "--profile",
        "observer-agent",
        "--dry-run",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "work_packet" not in payload


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
    assert "root-agent-workflow-verify-plan" in check_ids
    assert "root-agent-workflow-compliance" in check_ids
    assert "root-agent-workflow-status" in check_ids
    assert "agcp-drift" in check_ids
    assert "cockpit-agent-workflow-list" in check_ids
    assert "cockpit-agent-bootstrap" in check_ids
    assert "cockpit-agent-status" in check_ids
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
    assert "status" in report["next_commands"]
    assert "start" in report["next_commands"]
    assert "claim" in report["next_commands"]
    assert "verify" in report["next_commands"]
    assert "closeout" in report["next_commands"]
    assert "compliance" in report["next_commands"]
    assert "scoped_gate" in report["next_commands"]


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


def test_close_status_ok_requires_evidence(tmp_path: Path) -> None:
    """ADR-0209 A1: close --status ok without --evidence must fail."""
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
        "evidence gate",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]

    missing = _run_workflow(
        "--registry",
        str(registry),
        "close",
        run_id,
        "--status",
        "ok",
    )
    assert missing.returncode != 0
    assert "evidence" in (missing.stderr + missing.stdout).lower()

    # failed status may close without evidence (honest failure path)
    failed = _run_workflow(
        "--registry",
        str(registry),
        "close",
        run_id,
        "--status",
        "failed",
        "--json",
    )
    assert failed.returncode == 0, failed.stderr


def test_claim_adds_path_surface_locks_and_ledger_event(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    receipt = _write_affected_receipt(tmp_path, "workspace-root")
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "claim test",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]

    claim = _run_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--actor",
        "tester",
        "--path",
        "README.md",
        "--surface",
        "doc-ssot",
        "--affected-receipt",
        str(receipt),
        "--json",
    )
    assert claim.returncode == 0, claim.stderr
    payload = json.loads(claim.stdout)
    assert payload["paths"] == ["README.md"]
    assert payload["surfaces"] == ["doc-ssot"]
    assert "path:README.md" in payload["scopes"]
    assert "surface:doc-ssot" in payload["scopes"]

    run = _run_workflow("--registry", str(registry), "show-run", run_id, "--json")
    record = json.loads(run.stdout)
    assert record["claims"][0]["paths"] == ["README.md"]
    assert len(record["locks"]) == 3
    ledger = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "agent_workflow_claim" in ledger


def test_claim_rejects_dummy_nonexistent_and_tampered_receipts(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "reject false affected graph claims",
        "--json",
    )
    run_id = json.loads(start.stdout)["run_id"]

    for reference in (
        "dummy",
        f".omo/evidence/missing-{uuid.uuid4().hex}.json",
    ):
        rejected = _run_workflow(
            "--registry",
            str(registry),
            "claim",
            run_id,
            "--path",
            "README.md",
            "--affected-receipt",
            reference,
            "--json",
        )
        assert rejected.returncode == 2
        assert "receipt file does not exist" in rejected.stderr

    receipt = _write_affected_receipt(tmp_path, "workspace-root")
    receipt_path = ROOT / receipt
    payload = json.loads(receipt_path.read_text())
    payload["affected_projects"] = []
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    tampered = _run_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--path",
        "README.md",
        "--affected-receipt",
        str(receipt),
        "--json",
    )
    assert tampered.returncode == 2
    assert "receipt_hash mismatch" in tampered.stderr


def test_claim_rejects_receipt_missing_claimed_project(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    receipt = _write_affected_receipt(tmp_path, "workspace-root")
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "bind claimed project",
        "--json",
    )
    run_id = json.loads(start.stdout)["run_id"]

    rejected = _run_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--path",
        "projects/knowledge/gbrain/src/gbrain/api.py",
        "--affected-receipt",
        str(receipt),
        "--json",
    )

    assert rejected.returncode == 2
    assert "claimed projects missing" in rejected.stderr


def test_claim_accepts_cross_project_receipt_and_deprecated_path_alias(
    tmp_path: Path,
) -> None:
    registry = _write_control_plane_registry(tmp_path)
    receipt = _write_affected_receipt(tmp_path, "knowledge", "omo")
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "cross-project receipt",
        "--json",
    )
    run_id = json.loads(start.stdout)["run_id"]

    claim = _run_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--path",
        "projects/knowledge/gbrain/src/gbrain/api.py",
        "--path",
        "projects/omo/src/omo/workflow/cli.py",
        "--affected-receipt",
        str(receipt),
        "--json",
    )

    assert claim.returncode == 0, claim.stderr
    payload = json.loads(claim.stdout)
    assert payload["affected_graph"]["receipt_hash"]


def test_surface_only_claim_requires_workspace_root_receipt(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    project_receipt = _write_affected_receipt(tmp_path, "omo")
    root_receipt = _write_affected_receipt(tmp_path, "workspace-root")
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "surface-only receipt binding",
        "--json",
    )
    run_id = json.loads(start.stdout)["run_id"]

    rejected = _run_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--surface",
        "doc-ssot",
        "--affected-receipt",
        str(project_receipt),
        "--json",
    )
    assert rejected.returncode == 2
    assert "workspace-root" in rejected.stderr

    accepted = _run_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--surface",
        "doc-ssot",
        "--affected-receipt",
        str(root_receipt),
        "--json",
    )
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["surfaces"] == ["doc-ssot"]


def test_concurrent_claims_preserve_run_record(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    receipt = _write_affected_receipt(tmp_path, "workspace-root")
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "concurrent claim test",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]

    commands = [
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(WORKFLOW_MODULE_PATH),
            "--registry",
            str(registry),
            "claim",
            run_id,
            "--actor",
            "tester",
            "--path",
            path,
            "--affected-receipt",
            str(receipt),
            "--json",
        ]
        for path in ("README.md", "docs/README.md")
    ]
    processes = [
        subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for command in commands
    ]
    results = [process.communicate(timeout=60) for process in processes]

    for process, (stdout, stderr) in zip(processes, results, strict=True):
        assert process.returncode == 0, stderr or stdout

    run = _run_workflow("--registry", str(registry), "show-run", run_id, "--json")
    assert run.returncode == 0, run.stderr
    record = json.loads(run.stdout)
    claimed_paths = {tuple(claim["paths"]) for claim in record["claims"]}
    assert claimed_paths == {("README.md",), ("docs/README.md",)}
    assert len(record["locks"]) == 3


def test_verify_selects_diff_checks_for_explicit_files(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)

    verify = _run_workflow(
        "--registry",
        str(registry),
        "verify",
        "--file",
        "README.md",
        "--execute",
        "--json",
    )
    assert verify.returncode == 0, verify.stderr
    report = json.loads(verify.stdout)
    assert report["ok"] is True
    assert report["changed_files"] == ["README.md"]
    assert [item["id"] for item in report["checks"]] == ["readme-check"]
    assert report["checks"][0]["returncode"] == 0


def test_verify_reports_advisory_claim_gap(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "claim advisory test",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]

    verify = _run_workflow(
        "--registry",
        str(registry),
        "verify",
        run_id,
        "--file",
        "README.md",
        "--json",
    )

    assert verify.returncode == 0, verify.stderr
    report = json.loads(verify.stdout)
    assert report["ok"] is True
    assert report["claim_coverage"]["mode"] == "advisory"
    assert report["claim_coverage"]["missing_files"] == ["README.md"]
    assert report["claim_coverage"]["missing_required_files"] == []
    assert report["claim_coverage"]["missing_advisory_files"] == ["README.md"]


def test_verify_blocks_required_claim_tier(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    receipt = _write_affected_receipt(tmp_path, "workspace-root")
    text = registry.read_text(encoding="utf-8")
    registry.write_text(
        text.replace(
            "claim_policy:\n  mode: advisory\n  required_paths: [README.md]\n",
            """claim_policy:
  mode: advisory
  required_paths: [README.md]
  tiers:
    - id: core-required
      mode: required
      paths: [bin/agent-workflow.py]
""",
        ),
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
        "claim required tier test",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]

    blocked = _run_workflow(
        "--registry",
        str(registry),
        "verify",
        run_id,
        "--file",
        "bin/agent-workflow.py",
        "--json",
    )

    assert blocked.returncode == 1
    blocked_report = json.loads(blocked.stdout)
    assert blocked_report["ok"] is False
    assert blocked_report["claim_coverage"]["missing_required_files"] == ["bin/agent-workflow.py"]
    assert blocked_report["claim_coverage"]["missing_advisory_files"] == []

    claim = _run_workflow(
        "--registry",
        str(registry),
        "claim",
        run_id,
        "--path",
        "bin/agent-workflow.py",
        "--affected-receipt",
        str(receipt),
        "--json",
    )
    assert claim.returncode == 0, claim.stderr

    allowed = _run_workflow(
        "--registry",
        str(registry),
        "verify",
        run_id,
        "--file",
        "bin/agent-workflow.py",
        "--json",
    )

    assert allowed.returncode == 0, allowed.stderr
    allowed_report = json.loads(allowed.stdout)
    assert allowed_report["ok"] is True
    assert allowed_report["claim_coverage"]["missing_files"] == []


def test_read_only_workflow_skips_claim_policy(tmp_path: Path) -> None:
    """ADR-0209 A4: empty write surfaces exempt claim_policy write enforcement."""
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
claim_policy:
  mode: advisory
  required_paths: [README.md]
  tiers:
    - id: core-required
      mode: required
      paths: [bin/agent-workflow.py]
workflows:
  - id: observer-mini
    title: Observer
    purpose: Read-only
    allowed_lanes: [docs]
    lock_scopes: [observer-readonly]
    surfaces:
      read: [README.md]
      write: []
    agents:
      roles: [observer-agent]
    phases:
      preflight:
        - id: true-preflight
          mode: required
          command: [python, -c, pass]
      execute:
        - id: manual
          mode: manual
          command: [agent, read]
      verification:
        - id: true-verify
          mode: required
          command: [python, -c, pass]
      closeout:
        - id: true-closeout
          mode: required
          command: [python, -c, pass]
agent_profiles:
  observer-agent:
    purpose: read only
    allowed_workflows: [observer-mini]
    can_write_lanes: []
    closeout_required: []
""",
        encoding="utf-8",
    )
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "observer-mini",
        "--profile",
        "observer-agent",
        "--actor",
        "tester",
        "--objective",
        "read only claim exempt",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]

    verify = _run_workflow(
        "--registry",
        str(registry),
        "verify",
        run_id,
        "--file",
        "bin/agent-workflow.py",
        "--json",
    )
    assert verify.returncode == 0, verify.stderr
    report = json.loads(verify.stdout)
    assert report["ok"] is True
    assert report["claim_coverage"]["mode"] == "read_only_exempt"
    assert report["claim_coverage"]["missing_required_files"] == []


def test_observe_heals_missing_ledger_from_run_yaml(tmp_path: Path) -> None:
    """ADR-0209 A2: observe replays start event when ledger was trimmed."""
    registry = _write_control_plane_registry(tmp_path)
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "ledger heal",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]
    ledger = tmp_path / "events.jsonl"
    assert ledger.exists()
    # simulate external trim
    ledger.write_text("", encoding="utf-8")

    observe = _run_workflow(
        "--registry",
        str(registry),
        "observe",
        run_id,
        "--json",
    )
    assert observe.returncode == 0, observe.stderr
    report = json.loads(observe.stdout)
    kinds = [f.get("kind") for f in report.get("findings") or []]
    assert "ledger_healed_from_run" in kinds
    assert "ledger_missing_run" not in kinds
    text = ledger.read_text(encoding="utf-8")
    assert "agent_workflow_start" in text
    assert run_id in text
    assert "healed" in text


def test_closeout_verifies_observes_closes_and_compliance_passes(
    tmp_path: Path,
) -> None:
    registry = _write_control_plane_registry(tmp_path)
    production_effect_paths = [
        ROOT / ".agents/skills/workflow:mini/SKILL.md",
        ROOT / ".omo/state/agent-beliefs/index.yaml",
        ROOT / ".omo/_knowledge/workflow-mesh/events.jsonl",
    ]
    production_effects_before = {
        path: path.read_bytes() if path.is_file() else None for path in production_effect_paths
    }
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "closeout test",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]
    isolated_state = tmp_path / ".omo/state/agent-beliefs/index.yaml"
    isolated_state.parent.mkdir(parents=True, exist_ok=True)
    isolated_state.write_text(
        "beliefs:\n"
        "  - id: belief-0001\n"
        "    topic: workflow:mini\n"
        "    belief: seed isolated closeout\n",
        encoding="utf-8",
    )

    closeout = _run_workflow(
        "--registry",
        str(registry),
        "closeout",
        run_id,
        "--file",
        "README.md",
        "--evidence",
        "unit closeout",
        "--json",
    )
    assert closeout.returncode == 0, closeout.stderr
    report = json.loads(closeout.stdout)
    assert report["verify"]["ok"] is True
    assert report["observe"]["decision"] == "continue"
    assert report["run"]["status"] == "ok"
    assert report["run"]["released_locks"]
    assert not list((tmp_path / "locks").glob("*.lock.yaml"))

    compliance = _run_workflow("--registry", str(registry), "compliance", run_id, "--json")
    assert compliance.returncode == 0, compliance.stderr
    compliance_report = json.loads(compliance.stdout)
    assert compliance_report["decision"] == "continue"
    assert compliance_report["findings"] == []
    ledger = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "agent_workflow_verify" in ledger
    assert "agent_workflow_closeout" in ledger
    assert (tmp_path / ".agents/skills/workflow:mini/SKILL.md").is_file()
    assert (tmp_path / ".omo/_knowledge/workflow-mesh/events.jsonl").is_file()
    production_effects_after = {
        path: path.read_bytes() if path.is_file() else None for path in production_effect_paths
    }
    assert production_effects_after == production_effects_before


def test_compliance_accepts_legacy_close_event_after_verify(tmp_path: Path) -> None:
    registry = _write_control_plane_registry(tmp_path)
    start = _run_workflow(
        "--registry",
        str(registry),
        "start",
        "mini",
        "--actor",
        "tester",
        "--objective",
        "legacy close test",
        "--json",
    )
    assert start.returncode == 0, start.stderr
    run_id = json.loads(start.stdout)["run_id"]

    verify = _run_workflow("--registry", str(registry), "verify", run_id, "--file", "README.md", "--json")
    assert verify.returncode == 0, verify.stderr

    close = _run_workflow(
        "--registry",
        str(registry),
        "close",
        run_id,
        "--status",
        "ok",
        "--evidence",
        "legacy close evidence",
        "--json",
    )
    assert close.returncode == 0, close.stderr

    compliance = _run_workflow("--registry", str(registry), "compliance", run_id, "--json")

    assert compliance.returncode == 0, compliance.stderr
    compliance_report = json.loads(compliance.stdout)
    assert compliance_report["decision"] == "continue"
    assert compliance_report["findings"] == []
    ledger = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "agent_workflow_verify" in ledger
    assert "agent_workflow_close" in ledger


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
    assert module.classify("bin/compass_radar.py", set()) == "governance_code"
    assert module.classify("bin/ssot/doc-ssot-lint.py", set()) == "governance_code"
    assert module.classify("bin/mof/generate-brief.py", set()) == "governance_code"
    assert module.classify("bin/gac/governance-evolution.py", set()) == "governance_code"
    assert module.classify("bin/gac/state-stale-emit.py", set()) == "governance_code"
    assert module.classify("bin/README.md", set()) == "docs"
    assert module.classify("projects/cockpit/src/cockpit/commands/governance.py", set()) == "governance_code"
    assert (
        module.classify("projects/cockpit/src/cockpit/tests/test_agent_workflow_command.py", set()) == "governance_code"
    )
    assert module.classify("tests/test_governance_evolution.py", set()) == "governance_code"
    assert module.classify("bin/mof/project-layer-index.py", set()) == "governance_code"
    assert module.classify(".omo/_truth/registry/agent-workflows.yaml", set()) == "governance_code"
    assert module.classify(".agents/skills/project-governance/SKILL.md", set()) == "governance_code"
    assert module.classify("docs/generated/project-layer-index.md", set()) == "docs"


def test_change_lane_can_check_explicit_files() -> None:
    module = _load_module_from_source(LANE_MODULE_PATH, "change_lane_check")

    report = module.check(
        staged=True,
        files=[
            ".omo/_truth/registry/agent-workflows.yaml",
            "bin/agent-workflow.py",
        ],
    )

    assert report["ok"] is True
    assert report["lanes"] == ["governance_code"]


def test_change_lane_can_use_explicit_allowed_lanes_for_workflow_scopes() -> None:
    module = _load_module_from_source(LANE_MODULE_PATH, "change_lane_check")
    files = [
        ".omo/_truth/registry/governance-evolution-roadmap.yaml",
        "bin/gac/governance-evolution.py",
        "README.md",
    ]

    strict_report = module.check(staged=True, files=files)
    scoped_report = module.check(
        staged=True,
        files=files,
        allowed_lanes={"governance_state", "governance_code", "docs"},
    )

    assert strict_report["ok"] is False
    assert strict_report["lanes"] == ["docs", "governance_code", "governance_state"]
    assert scoped_report["ok"] is True
    assert scoped_report["allowed_lanes"] == [
        "docs",
        "governance_code",
        "governance_state",
    ]


def test_gac_gate_can_scope_change_lane_to_files(monkeypatch) -> None:
    module = _load_module_from_source(GAC_GATE_MODULE_PATH, "gac_local_gate")

    command = module.scoped_change_lane_command(
        "files",
        ["bin/agent-workflow.py", ".omo/_truth/registry/agent-workflows.yaml"],
        "",
    )

    assert command == [
        "bin/change-lane-check.py",
        "--file",
        ".omo/_truth/registry/agent-workflows.yaml",
        "--file",
        "bin/agent-workflow.py",
    ]

    monkeypatch.setenv("AGENT_WORKFLOW_MATCHED_FILES", json.dumps(["bin/gac/gac-local-gate.py"]))
    assert module.scoped_change_lane_command() == [
        "bin/change-lane-check.py",
        "--file",
        "bin/gac/gac-local-gate.py",
    ]


def test_status_command_exposes_agcp_control_plane_fields() -> None:
    result = _run_workflow("status", "--json")

    assert result.returncode in {0, 1}, result.stderr
    report = json.loads(result.stdout)
    assert "active_runs" in report
    assert "closed_runs" in report
    assert "lock_count" in report
    assert "stale_locks" in report
    assert "last_verify" in report
    assert "last_closeout" in report
    assert "compliance" in report
    assert "staged_lane" in report
    assert "claim_coverage" in report
    assert report["recommended_next"]


def _load_workflow_core():
    import importlib.util

    spec = importlib.util.spec_from_file_location("workflow_core_p0", ROOT / "projects/omo/src/omo/workflow/core.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_registry_supports_split_directory(tmp_path, monkeypatch) -> None:
    """ADR-0379 P0: PR #1016 把 agent-workflows.yaml 拆成目录 (workflows/profiles/adapters),
    load_registry 必须支持目录结构, 否则 agent-workflow 全链路 (start/claim/compliance) 不可用."""
    core = _load_workflow_core()
    load_registry, WorkflowError = core.load_registry, core.WorkflowError

    registry_dir = tmp_path / "agent-workflows"
    (registry_dir / "workflows").mkdir(parents=True)
    (registry_dir / "profiles").mkdir()
    (registry_dir / "adapters").mkdir()
    (registry_dir / "_root.yaml").write_text("version: 1\nclaim_policy:\n  mode: advisory\n", encoding="utf-8")
    (registry_dir / "workflows" / "project-code-change.yaml").write_text(
        "id: project-code-change\nrun_frequency: on_demand\nsurfaces:\n  write: [code]\n",
        encoding="utf-8",
    )
    (registry_dir / "profiles" / "_base.yaml").write_text(
        "agent_profiles:\n  docs-agent:\n    allowed_workflows: [project-doc-change]\n",
        encoding="utf-8",
    )
    (registry_dir / "adapters" / "gstack.yaml").write_text("gstack:\n  status: optional_adapter\n", encoding="utf-8")

    registry = load_registry(registry_dir)
    assert registry["claim_policy"]["mode"] == "advisory"
    assert [w["id"] for w in registry["workflows"]] == ["project-code-change"]
    assert "docs-agent" in registry["agent_profiles"]
    assert "gstack" in registry["external_patterns"]


def test_load_registry_split_directory_missing_workflows_raises(tmp_path) -> None:
    """P0: 目录结构缺 workflows/ → WorkflowError (不静默返回空)."""
    core = _load_workflow_core()
    load_registry, WorkflowError = core.load_registry, core.WorkflowError

    registry_dir = tmp_path / "agent-workflows"
    registry_dir.mkdir()
    (registry_dir / "_root.yaml").write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(WorkflowError):
        load_registry(registry_dir)


def test_compliance_auto_fix_orphan_lock() -> None:
    """compliance 应在检查前自动清理孤儿锁."""
    result = _run_root_workflow_strict("compliance")
    assert "orphan_lock" not in result.stdout
    assert "orphan_lock" not in result.stderr
