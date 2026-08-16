#!/usr/bin/env python3
"""Executable agent workflow runner for project-level governance."""
from __future__ import annotations

import sys
from pathlib import Path

# Resolve workspace and add omo src to PYTHONPATH dynamically
WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "projects/omo/src"))

from omo.workflow import (
    WORKSPACE,
    REGISTRY_PATH,
    AGENT_CLIS_PATH,
    AGORA_BOS_REGISTRY_PATH,
    AGCP_MOF_WORKFLOW_PATH,
    AGCP_MOF_BOSROUTE_PATH,
    AGCP_BOS_ROUTES,
    MOF_MODEL_PATH_PATTERN,
    MOF_DIFF_CHECK_IDS,
    ADAPTER_AUTHORITIES,
    INTEGRATION_AUTHORITIES,
    CLAIM_POLICY_MODES,
    RUN_UPDATE_LOCK_TIMEOUT_SECONDS,
    WorkflowError,
    SafeFormatDict,
    utc_now,
    load_registry,
    is_default_registry_path,
    load_yaml_document_with,
    workflow_by_id,
    workflow_roles,
    validate_agent_profile,
    context_from_args,
    substitute,
    command_display,
    normalize_repo_path,
    changed_files_from_git,
    path_matches,
    display_path,
    run_state_dir,
    lock_state_dir,
    ledger_path,
    workflow_rows,
    agent_rows,
    integration_rows,
    adapter_rows,
    diff_check_rows,
    validate_command,
    agcp_drift_findings,
    agcp_drift_check,
    lint_registry,
    print_lint,
    workflow_plan,
    print_plan,
    run_stage,
    sanitize_lock_name,
    run_update_lock,
    append_ledger_event,
    acquire_locks,
    release_locks,
    prune_stale_locks,
    scan_locks,
    run_file_for,
    start_run,
    spawn_run,
    trace_attribution,
    read_run,
    write_run,
    claim_run,
    close_run,
    closeout_run,
    run_check_command,
    normalize_claim_mode,
    claim_policy,
    claimed_paths,
    claim_covers_path,
    claim_coverage_report,
    build_verify_report,
    print_verify_report,
    parse_utc_timestamp,
    build_observe_report,
    observe,
    ledger_events,
    p74_solidification_report,
    compliance_report,
    print_compliance_report,
    last_ledger_event,
    staged_lane_report,
    recommended_next,
    build_status_report,
    print_status_report,
    run_doctor_check,
    build_doctor_report,
    print_doctor_report,
    doctor,
    health_summary,
    check_summary,
    suggest_workflows,
    _profile_hint,
    suggest_command,
    select_diff_checks,
    list_workflows,
    list_agents,
    list_integrations,
    list_adapters,
    handoff_markdown,
    bootstrap_report,
    print_bootstrap_report,
    build_parser,
    main,
)

from omo.workflow import cli as _wf_cli
from omo.workflow import diagnostics as _wf_diag
from omo.workflow import info as _wf_info
from omo.workflow import lifecycle as _wf_life

_PLAN_DIR = WORKSPACE / "bin" / "plan"
if str(_PLAN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLAN_DIR))
import chain_bind  # noqa: E402


_PENDING_BET = ""
_ORIG_START = _wf_life.start_run
_ORIG_BOOTSTRAP = _wf_info.bootstrap_report
_ORIG_PRINT_BOOTSTRAP = _wf_info.print_bootstrap_report
_ORIG_STATUS = _wf_diag.build_status_report
_ORIG_PRINT_STATUS = _wf_diag.print_status_report
_ORIG_MAIN = main


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
    global _PENDING_BET
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
                "agent-workflow: requirement-iteration start requires "
                f"--bet <BET-ID> ({', '.join(verdict.reasons)})",
                file=sys.stderr,
            )
            print(
                "  exempt: observer-audit, or "
                f"{chain_bind.GATE_ENV}=0 recorded waiver",
                file=sys.stderr,
            )
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
                        "agent-workflow: closeout blocked by vision→retro chain "
                        f"({', '.join(verdict.reasons)})",
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


if __name__ == "__main__":
    sys.exit(wrapped_main())
