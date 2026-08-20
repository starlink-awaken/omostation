#!/usr/bin/env python3
"""Executable agent workflow runner for project-level governance."""

from __future__ import annotations

import fnmatch
import importlib.util
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

# Resolve workspace and add omo src to PYTHONPATH dynamically
WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "projects/omo/src"))
sys.path.insert(0, str(WORKSPACE / "projects/ecos/src"))

from ecos.ssot.tools.work_packet_compiler import canonicalize, compute_packet_hash
from omo.workflow import (
    WORKSPACE,
    WorkflowError,
    load_registry,
    main,
    normalize_repo_path,
)
from omo.workflow import cli as _wf_cli
from omo.workflow import diagnostics as _wf_diag
from omo.workflow import info as _wf_info
from omo.workflow import lifecycle as _wf_life

_PLAN_DIR = WORKSPACE / "bin" / "plan"
if str(_PLAN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLAN_DIR))
import chain_bind

_PENDING_BET = ""
_PENDING_DELIVERY: dict[str, Any] | None = None
_ORIG_START = _wf_life.start_run
_ORIG_CLAIM = _wf_life.claim_run
_ORIG_BOOTSTRAP = _wf_info.bootstrap_report
_ORIG_PRINT_BOOTSTRAP = _wf_info.print_bootstrap_report
_ORIG_STATUS = _wf_diag.build_status_report
_ORIG_PRINT_STATUS = _wf_diag.print_status_report
_ORIG_MAIN = main

STARTABLE_BET_STATUSES = frozenset({"candidate", "pending", "blocked"})
_BET_LEDGER_MODULE: ModuleType | None = None


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


def _work_packet_from_bet(bet: dict[str, Any], binding: dict[str, str]) -> dict[str, Any]:
    """Project one ledger BET into the ECOS WorkPacket v2 invariant surface."""
    bet_id = str(bet["id"])
    risk = str(bet.get("risk_level") or "L1")
    risk_level = f"R{risk[1:]}" if len(risk) == 2 and risk[0] == "L" and risk[1].isdigit() else "R1"
    done_when = [str(item) for item in bet.get("done_when") or []]
    verify_commands = []
    for item in bet.get("verify") or []:
        command = item.get("cmd") if isinstance(item, dict) else item
        if isinstance(command, str) and command.strip():
            verify_commands.append([command.strip()])
    write_surfaces = sorted({str(item).strip().strip("/") for item in bet.get("write_surfaces") or [] if str(item).strip()})
    spec_surface = binding["spec_ref"].removeprefix("repo://")
    packet: dict[str, Any] = {
        "packet_id": f"WP-{bet_id}",
        "schema_version": "work-packet/v2",
        "blueprint_ref": "blueprint://multi-agent-execution-control/v1",
        "wave": str(bet.get("window") or ""),
        "bet_id": bet_id,
        "strategic_outcome": str(bet.get("goal") or ""),
        "objective": str(bet.get("goal") or bet.get("title") or ""),
        "why_now": f"priority={bet.get('priority', 'unspecified')}; appetite={bet.get('appetite', 'unspecified')}",
        "status": "active",
        "authority": {
            "strategist": "3y-bet-ledger",
            "human_gate": bool(bet.get("human_gate")),
            "risk_level": risk_level,
        },
        "scope": {
            "read_surfaces": ["docs/plans/3y-bet-ledger.yaml", spec_surface],
            "write_surfaces": write_surfaces,
            "non_goals": [str(item) for item in bet.get("non_goals") or []],
        },
        "dependencies": {
            "required_packets": [f"WP-{item}" for item in bet.get("depends_on") or []],
            "required_decisions": [binding["decision_ref"]],
        },
        "acceptance": {
            "done_when": [
                {
                    "id": f"AC-{index:02d}",
                    "assertion": assertion,
                    "evidence_type": "structured_report",
                }
                for index, assertion in enumerate(done_when, start=1)
            ],
            "verify_commands": verify_commands,
        },
        "rollback": {
            "strategy": str(bet.get("circuit_breaker") or "stop and escalate"),
            "data_migration": False,
        },
        "circuit_breaker": {
            "when": [str(bet.get("circuit_breaker") or "contract cannot be proven")],
            "action": "stop_and_escalate",
        },
        "spec_binding": binding,
    }
    # The ECOS compiler owns canonicalization and identity.  This wrapper only
    # projects existing BET fields into that contract.
    canonicalize(packet)
    return packet


def _prepare_bet_execution(
    bet_id: str,
    *,
    workspace: Path = WORKSPACE,
    require_startable: bool = True,
) -> dict[str, Any]:
    ledger = chain_bind.load_ledger(workspace)
    bet = chain_bind.bet_by_id(ledger, bet_id)
    if not isinstance(bet, dict):
        raise WorkflowError(f"BET_NOT_FOUND: {bet_id}")
    status = str(bet.get("status") or "")
    if require_startable and status not in STARTABLE_BET_STATUSES:
        raise WorkflowError(
            f"BET_STATUS_NOT_STARTABLE: {bet_id} status={status}; allowed={sorted(STARTABLE_BET_STATUSES)}"
        )
    ledger_contract = _load_bet_ledger_module()
    binding, errors = ledger_contract.validate_accepted_specification(bet, workspace=workspace)
    if errors or binding is None:
        raise WorkflowError("; ".join(errors or ["SPEC_BINDING_INVALID"]))
    packet = _work_packet_from_bet(bet, binding)
    packet_hash = compute_packet_hash(canonicalize(packet))
    return {
        "spec_binding": binding,
        "work_packet": packet,
        "work_packet_hash": packet_hash,
    }


def _surface_allows_path(surface: str, claimed_path: str) -> bool:
    normalized_surface = surface.strip().strip("/")
    if not normalized_surface:
        return False
    if any(token in normalized_surface for token in "*?["):
        return fnmatch.fnmatchcase(claimed_path, normalized_surface)
    if claimed_path == normalized_surface:
        return True
    surface_path = PurePosixPath(normalized_surface)
    looks_like_directory = "/" in normalized_surface and not surface_path.suffix
    return looks_like_directory and claimed_path.startswith(normalized_surface + "/")


def _validate_packet_run(
    payload: dict[str, Any],
    claimed_paths: list[str],
    *,
    claimed_surfaces: list[str] | None = None,
    workspace: Path = WORKSPACE,
) -> None:
    packet = payload.get("work_packet")
    packet_hash = payload.get("work_packet_hash")
    bet_id = str(payload.get("bet_id") or "")
    if packet is None and packet_hash is None:
        if bet_id:
            raise WorkflowError(f"WORK_PACKET_MISSING: bet-bound run {payload.get('run_id', '')}")
        return  # Explicit compatibility boundary for pre-spine/read-only runs.
    if not isinstance(packet, dict) or not isinstance(packet_hash, str):
        raise WorkflowError("WORK_PACKET_INVALID: packet and packet hash are required")
    measured_hash = compute_packet_hash(canonicalize(packet))
    if measured_hash != packet_hash:
        raise WorkflowError(
            f"WORK_PACKET_HASH_MISMATCH: declared={packet_hash} measured={measured_hash}"
        )
    if packet.get("bet_id") != bet_id:
        raise WorkflowError("WORK_PACKET_BET_MISMATCH: run and packet bet_id differ")

    rebuilt = _prepare_bet_execution(bet_id, workspace=workspace, require_startable=False)
    if rebuilt["work_packet_hash"] != packet_hash:
        raise WorkflowError(
            "WORK_PACKET_SOURCE_DRIFT: ledger/spec projection no longer matches the bound packet"
        )

    requested_surfaces = sorted({str(surface).strip() for surface in claimed_surfaces or [] if str(surface).strip()})
    if requested_surfaces:
        raise WorkflowError(
            "WORK_PACKET_SCOPE_MISMATCH: governance surfaces are not modeled by "
            f"scope.write_surfaces: {requested_surfaces}"
        )

    allowed = packet.get("scope", {}).get("write_surfaces", [])
    if not isinstance(allowed, list):
        raise WorkflowError("WORK_PACKET_INVALID: scope.write_surfaces must be a list")
    for raw_path in claimed_paths:
        claimed_path = normalize_repo_path(raw_path)
        if not any(_surface_allows_path(str(surface), claimed_path) for surface in allowed):
            raise WorkflowError(
                f"WORK_PACKET_SCOPE_MISMATCH: {claimed_path} is outside {allowed}"
            )


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


def _start_run_persist_bet(
    registry,
    workflow,
    context,
    objective,
    dry_run,
    force_lock,
    **kwargs,
):
    record = _ORIG_START(
        registry,
        workflow,
        context,
        objective,
        dry_run,
        force_lock,
        **kwargs,
    )
    bet_id = _PENDING_BET or str((context or {}).get("bet_id") or "")
    if bet_id:
        chain_bind.persist_bind_on_run(record, bet_id)
        if _PENDING_DELIVERY is None:
            raise WorkflowError(f"WORK_PACKET_MISSING: no prepared identity for {bet_id}")
        record.update(_PENDING_DELIVERY)
        run_path = record.get("path")
        if not dry_run and run_path:
            path = Path(run_path)
            if not path.is_absolute():
                path = WORKSPACE / path
            if path.is_file():
                payload = dict(record)
                payload.pop("path", None)
                chain_bind.write_run_file(path, payload)
    return record


def _claim_run_enforce_packet(
    registry,
    run_id,
    actor,
    paths,
    surfaces,
    force_lock,
    affected_hash=None,
    affected_receipt=None,
):
    _run_path, payload = _wf_life.read_run(registry, run_id)
    _validate_packet_run(payload, list(paths or []), claimed_surfaces=list(surfaces or []))
    return _ORIG_CLAIM(
        registry,
        run_id,
        actor,
        paths,
        surfaces,
        force_lock,
        affected_hash,
        affected_receipt,
    )


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
    _wf_life.start_run = _start_run_persist_bet
    _wf_cli.start_run = _start_run_persist_bet
    _wf_life.claim_run = _claim_run_enforce_packet
    _wf_cli.claim_run = _claim_run_enforce_packet
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
    global _PENDING_BET, _PENDING_DELIVERY
    argv = list(sys.argv[1:] if argv is None else argv)
    _install_patches()
    command, cmd_at = _find_command(argv)
    if command == "start":
        workflow_id = _positional_after(argv, cmd_at)
        bet_id = _flag(argv, "--bet")
        _PENDING_BET = bet_id
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
                _PENDING_DELIVERY = _prepare_bet_execution(bet_id)
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
        _PENDING_BET = ""
        _PENDING_DELIVERY = None


if __name__ == "__main__":
    sys.exit(wrapped_main())
