#!/usr/bin/env python3
"""Executable agent workflow runner for project-level governance."""

from __future__ import annotations

import importlib.util
import json
import os
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

        old_hash = str(payload.get("work_packet_hash") or "")
        payload["work_packet"] = prepared["work_packet"]
        payload["work_packet_hash"] = prepared["work_packet_hash"]
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
                _prepare_bet_execution(bet_id)
            except WorkflowError as exc:
                print(f"agent-workflow: {exc}", file=sys.stderr)
                return 1
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
        return int(_ORIG_MAIN() or 0)
    finally:
        sys.argv = previous


if __name__ == "__main__":
    sys.exit(wrapped_main())
