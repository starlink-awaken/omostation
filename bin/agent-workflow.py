#!/usr/bin/env python3
"""Executable agent workflow runner for project-level governance."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

# Resolve workspace and add omo src to PYTHONPATH dynamically
WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "projects/omo/src"))
sys.path.insert(0, str(WORKSPACE / "projects/ecos/src"))

from omo.workflow import (
    WORKSPACE,
    WorkflowError,
    load_registry,
    main,
)
from omo.workflow import cli as _wf_cli
from omo.workflow import diagnostics as _wf_diag
from omo.workflow import info as _wf_info
from omo.workflow import lifecycle as _wf_life

_PLAN_DIR = WORKSPACE / "bin" / "plan"
if str(_PLAN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLAN_DIR))
import chain_bind

_ORIG_BOOTSTRAP = _wf_info.bootstrap_report
_ORIG_PRINT_BOOTSTRAP = _wf_info.print_bootstrap_report
_ORIG_STATUS = _wf_diag.build_status_report
_ORIG_PRINT_STATUS = _wf_diag.print_status_report
_ORIG_MAIN = main

_BET_LEDGER_MODULE: ModuleType | None = None
_PROJECTION_MODULE: ModuleType | None = None
_CAPABILITY_SYNC_MODULE: ModuleType | None = None


def _load_bet_ledger_module() -> ModuleType:
    """Load the existing ledger contract without creating another authority."""
    global _BET_LEDGER_MODULE
    if _BET_LEDGER_MODULE is not None:
        return _BET_LEDGER_MODULE
    path = WORKSPACE / "bin/plan/bet-ledger.py"
    spec = importlib.util.spec_from_file_location("_agent_workflow_bet_ledger", path)
    if spec is None or spec.loader is None:
        raise WorkflowError(f"SPEC_BINDING_UNAVAILABLE: cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _BET_LEDGER_MODULE = module
    return module


def _load_projection_module() -> ModuleType:
    """Load the optional projection writer only for its explicit CLI commands."""
    global _PROJECTION_MODULE
    if _PROJECTION_MODULE is not None:
        return _PROJECTION_MODULE
    path = WORKSPACE / "lib/agent_workflow_projection.py"
    spec = importlib.util.spec_from_file_location("_agent_workflow_projection", path)
    if spec is None or spec.loader is None:
        raise WorkflowError(f"WORKFLOW_PROJECTION_UNAVAILABLE: cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _PROJECTION_MODULE = module
    return module


def _load_capability_sync_module() -> ModuleType:
    """Load the existing read-only capability resolver/inspector boundary."""
    global _CAPABILITY_SYNC_MODULE
    if _CAPABILITY_SYNC_MODULE is not None:
        return _CAPABILITY_SYNC_MODULE
    path = WORKSPACE / "bin/capability-sync.py"
    spec = importlib.util.spec_from_file_location("_agent_workflow_capability_sync", path)
    if spec is None or spec.loader is None:
        raise WorkflowError("CAPABILITY_PREFLIGHT_INSPECTOR_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - a missing mandatory inspector fails closed.
        sys.modules.pop(spec.name, None)
        raise WorkflowError("CAPABILITY_PREFLIGHT_INSPECTOR_UNAVAILABLE") from exc
    _CAPABILITY_SYNC_MODULE = module
    return module


def _prepare_bet_execution(
    bet_id: str,
    *,
    workspace: Path = WORKSPACE,
    require_startable: bool = True,
) -> dict[str, Any]:
    ledger_contract = _load_bet_ledger_module()
    try:
        return ledger_contract.prepare_bet_execution(
            bet_id,
            workspace=workspace,
            require_startable=require_startable,
        )
    except ledger_contract.SpecBindingContractError as exc:
        raise WorkflowError(str(exc)) from exc


def _validate_packet_run(
    payload: dict[str, Any],
    claimed_paths: list[str],
    *,
    claimed_surfaces: list[str] | None = None,
    workspace: Path = WORKSPACE,
) -> None:
    ledger_contract = _load_bet_ledger_module()
    try:
        ledger_contract.validate_work_packet_run(
            payload,
            claimed_paths,
            claimed_surfaces=claimed_surfaces,
            workspace=workspace,
        )
    except ledger_contract.SpecBindingContractError as exc:
        raise WorkflowError(str(exc)) from exc


def _clone_identity_for_preflight(workspace: Path) -> dict[str, str]:
    identity_path = workspace / ".git" / "agent-clone-identity.json"
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError("CAPABILITY_PREFLIGHT_CLONE_IDENTITY_REQUIRED") from exc
    actor_id = identity.get("actor_id") if isinstance(identity, dict) else None
    delivery_attempt_id = identity.get("delivery_attempt_id") if isinstance(identity, dict) else None
    valid_id = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    if (
        not isinstance(identity, dict)
        or identity.get("schema") != "agent-clone-identity/v2"
        or identity.get("ready") is not True
        or not isinstance(actor_id, str)
        or valid_id.fullmatch(actor_id) is None
        or identity.get("agent_id") != actor_id
        or not isinstance(delivery_attempt_id, str)
        or valid_id.fullmatch(delivery_attempt_id) is None
        or identity.get("canonical_root") != str(workspace.resolve())
        or identity.get("working_branch") != f"agent/{actor_id}--{delivery_attempt_id}"
    ):
        raise WorkflowError("CAPABILITY_PREFLIGHT_CLONE_IDENTITY_INVALID")
    return {
        "actor_id": actor_id,
        "delivery_attempt_id": delivery_attempt_id,
    }


def _capability_preflight(
    delivery_identity: dict[str, Any],
    run_id: str,
    *,
    workspace: Path = WORKSPACE,
    expected_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve and statically inspect each exact requirement without execution."""
    packet = delivery_identity.get("work_packet")
    requirements = packet.get("capability_requirements") if isinstance(packet, dict) else None
    digest = delivery_identity.get("capability_requirements_digest")
    if not isinstance(packet, dict) or not isinstance(requirements, list) or not isinstance(digest, str):
        raise WorkflowError("CAPABILITY_PREFLIGHT_REQUIREMENTS_INVALID")
    expected_digest = _load_bet_ledger_module().capability_requirements_digest(requirements)
    if digest != expected_digest:
        raise WorkflowError("CAPABILITY_PREFLIGHT_REQUIREMENTS_DIGEST_MISMATCH")

    clone = _clone_identity_for_preflight(workspace)
    binding = {
        "correlation_id": run_id,
        "workflow_run_id": run_id,
        "packet_id": packet.get("packet_id"),
        "packet_hash": delivery_identity.get("work_packet_hash"),
        "assignment_id": f"preflight:{run_id}:assignment",
        "dispatch_id": f"preflight:{run_id}:dispatch",
        "actor_id": clone["actor_id"],
        "delivery_attempt_id": clone["delivery_attempt_id"],
    }
    registry_path = workspace / "docs/generated/capability-registry.yaml"
    registry: dict[str, Any] | None = None
    registry_content: bytes | None = None

    def inspect_with_binding(inspection_binding: dict[str, Any]) -> list[dict[str, str]]:
        nonlocal registry, registry_content
        if not requirements:
            return []
        capability_sync = _load_capability_sync_module()
        inspected_rows: list[dict[str, str]] = []
        for requirement in requirements:
            if not isinstance(requirement, dict):
                raise WorkflowError("CAPABILITY_PREFLIGHT_REQUIREMENTS_INVALID")
            capability_id = requirement.get("capability_id")
            if not isinstance(capability_id, str) or ":" not in capability_id:
                raise WorkflowError("CAPABILITY_PREFLIGHT_REQUIREMENTS_INVALID")
            prefix = capability_id.split(":", 1)[0]
            try:
                if prefix in {"skill", "workflow"}:
                    receipt = capability_sync.inspect_native_capability(
                        root=workspace,
                        capability_id=capability_id,
                        registry={},
                        registry_content=b"",
                        binding=inspection_binding,
                    )
                else:
                    if registry is None or registry_content is None:
                        before = registry_path.stat()
                        registry_content = registry_path.read_bytes()
                        registry = capability_sync.load_registry(registry_path)
                        after = registry_path.stat()
                        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                            after.st_dev,
                            after.st_ino,
                            after.st_size,
                            after.st_mtime_ns,
                        ) or len(registry_content) != before.st_size:
                            raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_REJECTED")
                    resolution = capability_sync.resolve_capability(registry, capability_id=capability_id)
                    if resolution.status != "resolved":
                        raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_MISSING")
                    resolution_receipt = capability_sync.build_resolution_receipt(
                        resolution,
                        registry_content,
                        {"capability_id": capability_id},
                        binding=inspection_binding,
                        projection_metadata=registry,
                    )
                    receipt = capability_sync.inspect_native_capability(
                        root=workspace,
                        capability_id=capability_id,
                        registry=registry,
                        registry_content=registry_content,
                        resolution_receipt=resolution_receipt,
                    )
            except WorkflowError:
                raise
            except Exception as exc:  # noqa: BLE001 - source proof must fail closed.
                raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_REJECTED") from exc
            if not isinstance(receipt, dict) or receipt.get("status") != "inspected":
                raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_REJECTED")
            source_digest = receipt.get("source_digest")
            receipt_digest = receipt.get("receipt_digest")
            if (
                not isinstance(source_digest, str)
                or not source_digest.startswith("sha256:")
                or not isinstance(receipt_digest, str)
                or not receipt_digest.startswith("sha256:")
            ):
                raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_REJECTED")
            inspected_rows.append(
                {
                    "capability_id": capability_id,
                    "source_digest": source_digest,
                    "receipt_digest": receipt_digest,
                }
            )
        return inspected_rows

    if expected_preflight is not None:
        if expected_preflight.get("requirements_digest") != digest:
            raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_DRIFT")
        previous_binding = expected_preflight.get("binding")
        if not isinstance(previous_binding, dict) or any(
            previous_binding.get(field) != binding[field]
            for field in binding
            if field != "packet_hash"
        ):
            raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_DRIFT")
        comparable = inspect_with_binding(previous_binding)
        previous = expected_preflight.get("receipts")
        if not isinstance(previous, list) or previous != comparable:
            raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_DRIFT")
        inspected = comparable if previous_binding == binding else inspect_with_binding(binding)
    else:
        inspected = inspect_with_binding(binding)

    return {
        "requirements_digest": digest,
        "binding": binding,
        "receipts": inspected,
        "invoked": False,
        "value_indicator_policy": False,
    }


def _flag(argv: list[str], name: str) -> str:
    prefix = name + "="
    for index, item in enumerate(argv):
        if item == name and index + 1 < len(argv) and not argv[index + 1].startswith("-"):
            return argv[index + 1]
        if item.startswith(prefix):
            return item[len(prefix) :]
    return ""


def _find_command(argv: list[str]) -> tuple[str, int]:
    known = {
        "bootstrap",
        "context",
        "status",
        "start",
        "closeout",
        "close",
        "claim",
        "verify",
        "spawn",
        "handoff",
        "resume",
        "show-run",
        "observe",
        "compliance",
        "doctor",
        "suggest",
        "show",
        "run",
        "list",
        "agents",
        "integrations",
        "adapters",
        "trace",
        "lint",
        "refresh-packet",
        "projection-sync",
        "projection-check",
    }
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in known:
            return token, index
        if token.startswith("--") and index + 1 < len(argv) and not argv[index + 1].startswith("-"):
            index += 2
            continue
        index += 1
    return "", -1


def _positional_after(argv: list[str], cmd_index: int) -> str:
    index = cmd_index + 1
    while index < len(argv):
        token = argv[index]
        if token.startswith("--"):
            if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
                index += 2
                continue
            index += 1
            continue
        return token
    return ""


def _claimed_scope(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    surfaces: list[str] = []
    claims = payload.get("claims") or []
    if not isinstance(claims, list):
        raise WorkflowError("WORK_PACKET_REFRESH_CLAIMS_INVALID: claims must be a list")
    for claim in claims:
        if not isinstance(claim, dict):
            raise WorkflowError("WORK_PACKET_REFRESH_CLAIMS_INVALID: claim must be an object")
        for field, target in (("paths", paths), ("surfaces", surfaces)):
            values = claim.get(field) or []
            if not isinstance(values, list) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise WorkflowError(
                    f"WORK_PACKET_REFRESH_CLAIMS_INVALID: claim {field} must be a list of paths"
                )
            target.extend(values)
    return sorted(set(paths)), sorted(set(surfaces))


def _repo_ref_path(ref: str, *, label: str) -> str:
    if not ref.startswith("repo://"):
        raise WorkflowError(f"WORK_PACKET_REFRESH_SOURCE_INVALID: {label} must use repo://")
    path = ref.removeprefix("repo://").split("#", 1)[0].strip("/")
    if not path or path.startswith("../") or "/../" in path:
        raise WorkflowError(f"WORK_PACKET_REFRESH_SOURCE_INVALID: unsafe {label} path")
    return path


def _assert_packet_sources_at_ref(
    workspace: Path,
    prepared: dict[str, Any],
    *,
    authoritative_ref: str,
) -> None:
    source_paths = {
        "ledger": "docs/plans/3y-bet-ledger.yaml",
        "spec": _repo_ref_path(prepared["spec_binding"]["spec_ref"], label="spec_ref"),
        "instruction": _repo_ref_path(
            prepared["instruction_binding"]["instruction_ref"],
            label="instruction_ref",
        ),
    }
    for label, relative in source_paths.items():
        candidate = workspace / relative
        try:
            working_bytes = candidate.read_bytes()
        except OSError as exc:
            raise WorkflowError(f"WORK_PACKET_REFRESH_SOURCE_UNREADABLE: {label}: {exc}") from exc
        try:
            probe = subprocess.run(
                ["git", "-C", str(workspace), "show", f"{authoritative_ref}:{relative}"],
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise WorkflowError(f"WORK_PACKET_REFRESH_SOURCE_UNPROVABLE: {label}: {exc}") from exc
        if probe.returncode != 0:
            raise WorkflowError(
                f"WORK_PACKET_REFRESH_SOURCE_UNPROVABLE: {label} is unavailable at {authoritative_ref}"
            )
        if probe.stdout != working_bytes:
            raise WorkflowError(
                f"WORK_PACKET_REFRESH_SOURCE_UNMERGED: {label} differs from {authoritative_ref}"
            )


def _resolve_authoritative_revision(workspace: Path, ref: str) -> str:
    try:
        probe = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--verify", f"{ref}^{{commit}}"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as exc:
        raise WorkflowError(f"WORK_PACKET_REFRESH_SOURCE_UNPROVABLE: ref {ref}: {exc}") from exc
    revision = probe.stdout.strip()
    if probe.returncode != 0 or len(revision) not in {40, 64} or any(
        character not in "0123456789abcdefABCDEF" for character in revision
    ):
        raise WorkflowError(f"WORK_PACKET_REFRESH_SOURCE_UNPROVABLE: ref {ref}")
    return revision.lower()


def _restore_run_bytes(path: Path, original: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.refresh-rollback-",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _refresh_packet_run(
    registry: dict[str, Any],
    run_id: str,
    *,
    workspace: Path = WORKSPACE,
    authoritative_ref: str | None = "origin/main",
) -> dict[str, Any]:
    """Refresh only the WorkPacket projection of an active, identity-stable run."""
    if not run_id:
        raise WorkflowError("WORK_PACKET_REFRESH_RUN_REQUIRED: missing run_id")
    authoritative_revision = (
        _resolve_authoritative_revision(workspace, authoritative_ref)
        if authoritative_ref is not None
        else None
    )
    with _wf_life.run_update_lock(registry, run_id):
        path, payload = _wf_life.read_run(registry, run_id)
        original_bytes = path.read_bytes()
        if payload.get("status") != "active":
            raise WorkflowError(f"WORK_PACKET_REFRESH_INACTIVE: {run_id}")
        bet_id = str(payload.get("bet_id") or "")
        if not bet_id:
            raise WorkflowError("WORK_PACKET_REFRESH_UNBOUND: run has no bet_id")

        prepared = _prepare_bet_execution(
            bet_id,
            workspace=workspace,
            require_startable=False,
        )
        if authoritative_revision is not None:
            _assert_packet_sources_at_ref(
                workspace,
                prepared,
                authoritative_ref=authoritative_revision,
            )
        if payload.get("spec_binding") != prepared["spec_binding"]:
            raise WorkflowError("WORK_PACKET_REFRESH_SPEC_DRIFT: accepted Spec binding changed")
        if payload.get("instruction_binding") != prepared["instruction_binding"]:
            raise WorkflowError("WORK_PACKET_REFRESH_INSTRUCTION_DRIFT: instruction binding changed")

        candidate = dict(payload)
        candidate["work_packet"] = prepared["work_packet"]
        candidate["work_packet_hash"] = prepared["work_packet_hash"]
        payload_has_capabilities = "capability_requirements_digest" in payload
        prepared_has_capabilities = "capability_requirements_digest" in prepared
        if payload_has_capabilities != prepared_has_capabilities:
            raise WorkflowError("CAPABILITY_PREFLIGHT_SOURCE_DRIFT")
        refreshed_preflight = None
        if prepared_has_capabilities:
            refreshed_preflight = _capability_preflight(
                prepared,
                run_id,
                workspace=workspace,
                expected_preflight=payload.get("capability_preflight"),
            )
            candidate["capability_requirements_digest"] = prepared["capability_requirements_digest"]
            candidate["capability_preflight"] = refreshed_preflight
        claimed_paths, claimed_surfaces = _claimed_scope(payload)
        _validate_packet_run(
            candidate,
            claimed_paths,
            claimed_surfaces=claimed_surfaces,
            workspace=workspace,
        )

        # Rebuild once more before mutation so a concurrent ledger/spec edit
        # cannot silently bind a mixed-source packet.
        confirmed = _prepare_bet_execution(
            bet_id,
            workspace=workspace,
            require_startable=False,
        )
        if confirmed != prepared:
            raise WorkflowError("WORK_PACKET_REFRESH_SOURCE_RACED: packet sources changed during refresh")
        if authoritative_revision is not None:
            _assert_packet_sources_at_ref(
                workspace,
                confirmed,
                authoritative_ref=authoritative_revision,
            )
        if prepared_has_capabilities:
            confirmed_preflight = _capability_preflight(
                confirmed,
                run_id,
                workspace=workspace,
                expected_preflight=payload.get("capability_preflight"),
            )
            if confirmed_preflight != refreshed_preflight:
                raise WorkflowError("WORK_PACKET_REFRESH_SOURCE_RACED: capability source changed during refresh")

        old_hash = str(payload.get("work_packet_hash") or "")
        payload["work_packet"] = prepared["work_packet"]
        payload["work_packet_hash"] = prepared["work_packet_hash"]
        if prepared_has_capabilities:
            payload["capability_requirements_digest"] = prepared["capability_requirements_digest"]
            payload["capability_preflight"] = refreshed_preflight
        _wf_life.write_run(path, payload)
        try:
            _wf_life.append_ledger_event(
                registry,
                {
                    "event": "agent_workflow_packet_refreshed",
                    "run_id": run_id,
                    "bet_id": bet_id,
                    "old_work_packet_hash": old_hash,
                    "work_packet_hash": prepared["work_packet_hash"],
                    "authoritative_revision": authoritative_revision,
                },
            )
        except OSError as exc:
            try:
                _restore_run_bytes(path, original_bytes)
            except OSError as rollback_exc:
                raise WorkflowError(
                    "WORK_PACKET_REFRESH_AUDIT_AND_ROLLBACK_FAILED: "
                    f"audit={exc}; rollback={rollback_exc}"
                ) from rollback_exc
            raise WorkflowError(f"WORK_PACKET_REFRESH_AUDIT_FAILED: {exc}") from exc

        return {
            "ok": True,
            "reason": "work_packet_refreshed",
            "run_id": run_id,
            "bet_id": bet_id,
            "old_work_packet_hash": old_hash,
            "work_packet_hash": prepared["work_packet_hash"],
            "authoritative_revision": authoritative_revision,
            "claimed_paths": claimed_paths,
            "claimed_surfaces": claimed_surfaces,
        }


def _bootstrap_with_chain(registry, include_health, include_agcp_drift=True):
    report = _ORIG_BOOTSTRAP(registry, include_health, include_agcp_drift)
    return chain_bind.inject_perception(report, WORKSPACE)


def _print_bootstrap_with_chain(report, as_json):
    if not as_json:
        chain = report.get("chain") or chain_bind.perception_fields(WORKSPACE)
        chain_bind.print_perception(chain)
    return _ORIG_PRINT_BOOTSTRAP(report, as_json)


def _status_with_chain(registry, include_health, include_agcp_drift=True):
    report = _ORIG_STATUS(registry, include_health, include_agcp_drift)
    return chain_bind.inject_perception(report, WORKSPACE)


def _print_status_with_chain(report, as_json):
    if not as_json:
        chain = report.get("chain") or chain_bind.perception_fields(WORKSPACE)
        chain_bind.print_perception(chain)
    return _ORIG_PRINT_STATUS(report, as_json)


def _install_patches() -> None:
    _wf_info.bootstrap_report = _bootstrap_with_chain
    _wf_cli.bootstrap_report = _bootstrap_with_chain
    _wf_info.print_bootstrap_report = _print_bootstrap_with_chain
    _wf_cli.print_bootstrap_report = _print_bootstrap_with_chain
    _wf_diag.build_status_report = _status_with_chain
    _wf_cli.build_status_report = _status_with_chain
    _wf_diag.print_status_report = _print_status_with_chain
    _wf_cli.print_status_report = _print_status_with_chain


def wrapped_main(argv: list[str] | None = None) -> int:
    """Root wrapper: require --bet, persist bet_id, halt unbound ok-closeout."""
    argv = list(sys.argv[1:] if argv is None else argv)
    _install_patches()
    command, cmd_at = _find_command(argv)
    start_preflight = None
    if command in {"projection-sync", "projection-check"}:
        if "--help" in argv or "-h" in argv:
            print(
                f"usage: agent-workflow.py {command} "
                "[--registry DIRECTORY] [--projection FILE] [--json]"
            )
            return 0
        registry_arg = _flag(argv, "--registry")
        projection_arg = _flag(argv, "--projection")
        registry_path = Path(registry_arg) if registry_arg else WORKSPACE / ".omo/_truth/registry/agent-workflows"
        projection_path = (
            Path(projection_arg)
            if projection_arg
            else WORKSPACE / ".omo/_truth/registry/agent-workflows.yaml"
        )
        try:
            projection_module = _load_projection_module()
        except WorkflowError as exc:
            print(f"agent-workflow: {exc}", file=sys.stderr)
            return 1
        try:
            registry, registry_digest = projection_module.load_registry_snapshot(
                load_registry,
                registry_path,
            )
            operation = (
                projection_module.sync_projection
                if command == "projection-sync"
                else projection_module.check_projection
            )
            result = operation(
                registry,
                registry_path,
                projection_path,
                source_digest_bound=registry_digest,
            )
        except (projection_module.ProjectionError, WorkflowError) as exc:
            print(f"agent-workflow: {exc}", file=sys.stderr)
            return 1
        if "--json" in argv:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"{result['reason']}: {result['source_digest']}")
        return 0
    if command == "refresh-packet":
        if "--help" in argv or "-h" in argv:
            print("usage: agent-workflow.py refresh-packet RUN_ID [--registry PATH] [--json]")
            return 0
        run_id = _positional_after(argv, cmd_at)
        registry_arg = _flag(argv, "--registry")
        try:
            registry = load_registry(Path(registry_arg)) if registry_arg else load_registry()
            result = _refresh_packet_run(
                registry,
                run_id,
                workspace=_wf_life.registry_workspace_root(registry),
            )
        except WorkflowError as exc:
            print(f"agent-workflow: {exc}", file=sys.stderr)
            return 1
        if "--json" in argv:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(
                f"refreshed {run_id}: {result['old_work_packet_hash']} -> "
                f"{result['work_packet_hash']}"
            )
        return 0
    if command == "start":
        workflow_id = _positional_after(argv, cmd_at)
        bet_id = _flag(argv, "--bet")
        parent_run_id = _flag(argv, "--parent-run")
        if parent_run_id:
            try:
                registry_arg = _flag(argv, "--registry")
                registry = load_registry(Path(registry_arg)) if registry_arg else load_registry()
                bet_id, _identity, _parent_agent = _wf_life.resolve_parent_delivery_identity(
                    registry,
                    parent_run_id,
                    bet_id,
                )
            except WorkflowError as exc:
                print(f"agent-workflow: {exc}", file=sys.stderr)
                return 1
        verdict = chain_bind.start_requires_bet(workflow_id, bet_id)
        if not verdict.ok:
            print(
                f"agent-workflow: requirement-iteration start requires --bet <BET-ID> ({', '.join(verdict.reasons)})",
                file=sys.stderr,
            )
            print(
                f"  exempt: observer-audit, or {chain_bind.GATE_ENV}=0 recorded waiver",
                file=sys.stderr,
            )
            return 1
        if bet_id:
            try:
                prepared = _prepare_bet_execution(bet_id)
                if not parent_run_id and "capability_requirements_digest" in prepared:
                    def root_start_preflight(run_id: str, _identity: dict[str, Any]) -> dict[str, Any]:
                        return _capability_preflight(prepared, run_id, workspace=WORKSPACE)

                    start_preflight = root_start_preflight
            except WorkflowError as exc:
                print(f"agent-workflow: {exc}", file=sys.stderr)
                return 1

        # Optimization 4: Edge-First Triage via AetherForge
        objective = _flag(argv, "--objective")
        if objective:
            print("\n[Edge-First] 🧠 正在通过本地 AetherForge (omlxc) 评估意图复杂度与预热上下文...", file=sys.stderr)
            try:
                triage_res = subprocess.run(
                    ["uv", "run", "omlxc", "fabric", "triage", objective],
                    cwd=str(WORKSPACE / "projects" / "omlxc"),
                    capture_output=True,
                    text=True
                )
                if triage_res.returncode == 0:
                    print(triage_res.stdout, file=sys.stderr)
                else:
                    print(f"  [WARN] 本地分诊引擎未就绪，降级到标准流程。({triage_res.stderr.strip()})", file=sys.stderr)
            except Exception as e:
                print(f"  [WARN] Triage skipped: {e}", file=sys.stderr)

    elif command == "closeout":
        run_id = _positional_after(argv, cmd_at)
        status = _flag(argv, "--status") or "ok"
        if run_id and status == "ok":
            try:
                _path, payload = _wf_life.read_run(load_registry(), run_id)
            except Exception:
                payload = None
            if isinstance(payload, dict):
                verdict = chain_bind.evaluate_closeout(payload, WORKSPACE, status=status)
                if not verdict.ok:
                    print(
                        f"agent-workflow: closeout blocked by vision→retro chain ({', '.join(verdict.reasons)})",
                        file=sys.stderr,
                    )
                    print(
                        "  bind: start --bet, Plan north-star pointer, retro file",
                        file=sys.stderr,
                    )
                    return 1
    try:
        previous = sys.argv
        sys.argv = [sys.argv[0], *argv]
        return int(_ORIG_MAIN(start_preflight=start_preflight) or 0)
    finally:
        sys.argv = previous



def _post_closeout_pitfall_hint():
    """BET-Y1Q3-T10-09 后续: closeout 后如果有 blockers 提示记录 pitfalls."""
    import sys as _sys
    argv_str = " ".join(_sys.argv)
    if "closeout" not in argv_str:
        return
    # 检查是否有 blockers 相关输出
    # 简化实现: 打印提示让 agent 自行决定是否记录
    print("\n💡 [error-knowledge] 如果本次 closeout 有 blockers/discovered 项，"
          "建议记录到知识库:\n"
          "  python3 bin/gac/error-knowledge.py record \\\n"
          "    --category <submodule|cron|gate|scoring|coordination|environment|measurement> \\\n"
          "    --title \"...\" --symptom \"...\" --solution \"...\"\n",
          file=_sys.stderr)

if __name__ == "__main__":
    _post_closeout_pitfall_hint()
    sys.exit(wrapped_main())
