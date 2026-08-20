#!/usr/bin/env python3
"""Executable agent workflow runner for project-level governance."""

from __future__ import annotations

import importlib.util
import sys
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
