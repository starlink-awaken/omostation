#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .omo_admission import evaluate_worker_envelope, request_conditional_approval
from .omo_governance import propose_truth_mutation
from .omo_contract_request import (
    build_contract_proposal,
    build_contract_request,
    contract_request_ref,
)
from .omo_io import write_text_atomic, write_yaml_atomic
from .omo_handoff_index import write_handoff_index
from .omo_metrics import write_worker_utilization_summary
from .omo_promotion_approval import evaluate_promotion_approval
from .omo_promotion_history import build_promotion_history
from .omo_promotion_request import (
    build_promotion_approval_proposal,
    build_promotion_approval_request,
    promotion_approval_ref,
)
from .omo_promotion_approval_status import (
    build_promotion_approval_status_packet,
    render_promotion_approval_status_markdown,
)
from .omo_promotion_approval_history import build_promotion_approval_history
from .omo_promotion_approval_analytics import build_promotion_approval_analytics_packet
from .omo_governance_overlay import build_governance_overlay_status
from .omo_governance_overlay_approval_prep import (
    build_governance_overlay_approval_prep_history,
    build_governance_overlay_approval_prep_status,
)
from .omo_governance_overlay_approval_prep_aging import (
    build_governance_overlay_approval_prep_aging,
)
from .omo_governance_overlay_approval_prep_analytics import (
    build_governance_overlay_approval_prep_analytics,
)
from .omo_governance_overlay_approval_prep_diff import (
    build_governance_overlay_approval_prep_diff,
)
from .omo_governance_overlay_approval_prep_trend import (
    build_governance_overlay_approval_prep_trend,
)
from .omo_governance_overlay_loop import plan_governance_overlay_cycle
from .omo_governance_overlay_targets import evaluate_governance_overlay_planned_target
from .omo_promotion_readiness import (
    build_promotion_readiness_packet,
    render_promotion_readiness_markdown,
)
from .omo_rules import evaluate_rule_bundle
from .omo_rollout import accept_rollout_envelope, evaluate_rollout_envelope
from .omo_redaction import redact_sensitive_text
from .omo_task_schema import (
    validate_active_tasks,
    validate_planned_tasks,
    validate_task_file,
)


# ── Extracted submodules ────────────────────────────────────────────────────
from .omo_worker_core import (
    _omo_path,
    _load_yaml,
    _write_yaml,
    _utc_now,
)
from .omo_worker_dispatch import (
    dispatch_task,
    reclaim_task,
    _worker_gc,
)
from .omo_worker_promotion import (
    _promotion_eval,
    _print_task_promotion_eval,
    _promotion_stamp,
    _task_has_task_specific_promotion_approval,
    _execute_governance_overlay_target_actions,
    _sync_omo_state,
    _apply_task_promotion,
    _request_task_promotion_approval,
    _request_task_contract_declaration,
    _request_task_contract_declaration_record,
    _request_task_promotion_approval_record,
    _write_task_promotion_history,
    _promotion_readiness_entry,
    _write_task_promotion_readiness,
    _proposal_status,
    _promotion_approval_status_entry,
    _write_task_promotion_approval_status,
    _write_task_promotion_approval_history,
    _write_task_promotion_approval_analytics,
    _write_task_governance_overlay_status,
    _write_task_governance_overlay_approval_prep_status,
    _write_task_governance_overlay_approval_prep_history,
    _write_task_governance_overlay_approval_prep_analytics,
    _write_task_governance_overlay_approval_prep_trend,
    _write_task_governance_overlay_approval_prep_aging,
    _write_task_governance_overlay_approval_prep_diff,
    _write_task_governance_overlay_run_next,
)

def collect_worker_status(
    root: Path, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    active_dir = _omo_path(root, omo_dir) / "tasks" / "active"
    runs: list[dict[str, object]] = []

    for task_file in sorted(active_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        run_ref = task.get("run_ref")
        if not run_ref:
            continue

        dispatch_path = root / run_ref
        if not dispatch_path.exists():
            continue

        dispatch = _load_yaml(dispatch_path)
        runs.append(
            {
                "task_id": dispatch.get("task_id", task.get("id")),
                "worker_id": dispatch.get("worker_id"),
                "dispatch_state": dispatch.get("dispatch_state"),
                "checkpoint_refs": dispatch.get("execution", {}).get(
                    "checkpoint_refs", []
                ),
                "reclaim_ref": dispatch.get("reclaim", {}).get("note_ref"),
                "review_ref": dispatch.get("handoff", {}).get("output_summary_ref"),
                "lease": dispatch.get("lease", {}),
            }
        )

    return {
        "active_dispatches": len(runs),
        "runs": runs,
    }


def update_dispatch_checkpoint(
    root: Path,
    dispatch_id: str,
    completed_step: str,
    changed_files: list[str],
    note: str,
    now: str | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, object]:
    dispatch_path = _find_dispatch_file(
        _omo_path(root, omo_dir) / "workers" / "runs", dispatch_id
    )
    dispatch = _load_yaml(dispatch_path)
    checkpoint_ref = dispatch.get("execution", {}).get("checkpoint_refs", [None])[-1]
    if not checkpoint_ref:
        raise ValueError(f"dispatch {dispatch_id} has no checkpoint ref")

    timestamp = now or _utc_now()
    changed_file_lines = [f"- `{path}`" for path in changed_files] or ["- None"]
    checkpoint_lines = [
        "# Checkpoint Note",
        "",
        "## Last completed step",
        "",
        completed_step,
        "",
        "## Changed files",
        "",
        *changed_file_lines,
        "",
        "## Operator note",
        "",
        note,
        "",
    ]
    write_text_atomic(root / checkpoint_ref, "\n".join(checkpoint_lines))

    dispatch["dispatch_state"] = "checkpointed"
    dispatch["lease"]["last_checkpoint_at"] = timestamp
    dispatch["lease"]["last_material_write_at"] = timestamp
    _write_yaml(dispatch_path, dispatch)
    return dispatch


def scan_runtime_watchdog(
    root: Path, now: str | None = None, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    current_time = _parse_iso8601(now) or datetime.now(timezone.utc)
    status = collect_worker_status(root, omo_dir=omo_dir)
    runs: list[dict[str, object]] = []
    counts = {"healthy": 0, "warning": 0, "stale": 0, "reclaim_due": 0}

    for run in status["runs"]:
        lease = run.get("lease", {})
        last_seen = _parse_iso8601(
            lease.get("last_material_write_at")
        ) or _parse_iso8601(lease.get("last_checkpoint_at"))
        age_seconds = (
            int((current_time - last_seen).total_seconds()) if last_seen else None
        )
        health = "healthy"
        if age_seconds is not None:
            if age_seconds >= lease.get("reclaim_after_seconds", 0):
                health = "reclaim_due"
            elif age_seconds >= lease.get("lease_expired_after_seconds", 0):
                health = "stale"
            elif age_seconds >= lease.get("warning_after_seconds", 0):
                health = "warning"
        counts[health] += 1
        runs.append(
            {
                **run,
                "age_seconds": age_seconds,
                "health": health,
            }
        )

    return {"counts": counts, "runs": runs}



def _print_worker_status(root: Path, omo_dir: str | Path = ".omo") -> int:
    status = collect_worker_status(root, omo_dir=omo_dir)
    print(f"active_dispatches={status['active_dispatches']}")
    for run in status["runs"]:
        print(
            f"{run['task_id']} worker={run['worker_id']} "
            f"state={run['dispatch_state']} checkpoints={len(run['checkpoint_refs'])} "
            f"reclaim={run['reclaim_ref']}"
        )
    return 0


def _print_worker_watchdog(
    root: Path, now: str | None = None, omo_dir: str | Path = ".omo"
) -> int:
    watchdog = scan_runtime_watchdog(root, now=now, omo_dir=omo_dir)
    counts = watchdog["counts"]
    print(
        f"healthy={counts['healthy']} warning={counts['warning']} "
        f"stale={counts['stale']} reclaim_due={counts['reclaim_due']}"
    )
    for run in watchdog["runs"]:
        print(
            f"{run['task_id']} worker={run['worker_id']} state={run['dispatch_state']} "
            f"health={run['health']} age_seconds={run['age_seconds']}"
        )
    return 0


def _print_worker_admission_eval(
    root: Path, envelope_ref: str, matrix_ref: str | None = None
) -> int:
    result = evaluate_worker_envelope(
        root,
        Path(envelope_ref),
        matrix_ref=Path(matrix_ref) if matrix_ref else None,
    )
    print(
        f"action={result['action']} membership={result['membership_ref']} "
        f"decision={result['decision']} approval_required={result['approval_required']}"
    )
    return 0


def _request_worker_admission_approval(
    root: Path,
    envelope_ref: str,
    requested_by: str,
    now: str,
) -> int:
    result = request_conditional_approval(
        root, Path(envelope_ref), requested_by=requested_by, now=now
    )
    print(
        f"proposal={result['proposal_id']} approval_ref={result['approval_ref']} decision={result['decision']}"
    )
    return 0


def _print_worker_rollout_eval(root: Path, envelope_ref: str) -> int:
    result = evaluate_rollout_envelope(root, Path(envelope_ref))
    print(
        f"action={result['action']} approval={result['approval_status']} "
        f"decision={result['decision']} acceptance_ready={result['acceptance_ready']}"
    )
    return 0


def _accept_worker_rollout(
    root: Path, envelope_ref: str, accepted_by: str, now: str
) -> int:
    result = accept_rollout_envelope(
        root, Path(envelope_ref), accepted_by=accepted_by, now=now
    )
    print(f"acceptance_ref={result['acceptance_ref']} decision={result['decision']}")
    return 0


def _print_worker_rules_eval(root: Path, envelope_ref: str) -> int:
    result = evaluate_rule_bundle(root, Path(envelope_ref))
    delivery_contract = result.get("delivery_contract_ref")
    delivery_segment = (
        f" delivery_contract={delivery_contract}" if delivery_contract else ""
    )
    print(
        f"action={result['action']} registry={result['registry_ref']} "
        f"data_policy={result['data_policy_ref']}{delivery_segment} "
        f"runtime_boundary={result['runtime_boundary_ref']}"
    )
    return 0



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    worker_parser = subparsers.add_parser("worker")
    worker_sub = worker_parser.add_subparsers(dest="worker_command", required=True)

    dispatch_parser = worker_sub.add_parser("dispatch")
    dispatch_parser.add_argument("task_id")
    dispatch_parser.add_argument("--worker", required=True, dest="worker_id")
    dispatch_parser.add_argument(
        "--write-path", action="append", default=[], dest="write_paths"
    )
    dispatch_parser.add_argument("--launch", action="store_true")
    dispatch_parser.add_argument("--transport", default="cli_prompt")
    dispatch_parser.add_argument("--omo-dir", default=".omo")

    reclaim_parser = worker_sub.add_parser("reclaim")
    reclaim_parser.add_argument("task_id")
    reclaim_parser.add_argument(
        "--successor", required=True, dest="successor_worker_id"
    )
    reclaim_parser.add_argument("--reason", required=True)
    reclaim_parser.add_argument(
        "--write-path", action="append", default=[], dest="write_paths"
    )
    reclaim_parser.add_argument("--launch", action="store_true")
    reclaim_parser.add_argument("--transport", default="cli_prompt")
    reclaim_parser.add_argument("--omo-dir", default=".omo")

    gc_parser = worker_sub.add_parser("gc")
    gc_parser.add_argument(
        "--dry-run", action="store_true", help="Just list, don't delete"
    )
    gc_parser.add_argument(
        "--retain",
        type=int,
        default=50,
        help="Number of latest dispatch runs to retain",
    )
    gc_parser.add_argument("--omo-dir", default=".omo")

    status_parser = worker_sub.add_parser("status")
    status_parser.add_argument("--omo-dir", default=".omo")
    baseline_parser = worker_sub.add_parser("baseline")
    baseline_parser.add_argument("--root", default=".")
    handoff_parser = worker_sub.add_parser("handoff-index")
    handoff_parser.add_argument("task_id")
    watchdog_parser = worker_sub.add_parser("watchdog")
    watchdog_parser.add_argument("--now")
    watchdog_parser.add_argument("--omo-dir", default=".omo")
    admission_parser = worker_sub.add_parser("admission-eval")
    admission_parser.add_argument("envelope_ref")
    admission_parser.add_argument("--matrix-ref")
    request_approval_parser = worker_sub.add_parser("admission-request-approval")
    request_approval_parser.add_argument("envelope_ref")
    request_approval_parser.add_argument("--requested-by", required=True)
    request_approval_parser.add_argument("--now", required=True)
    rules_eval_parser = worker_sub.add_parser("rules-eval")
    rules_eval_parser.add_argument("envelope_ref")
    rollout_eval_parser = worker_sub.add_parser("rollout-eval")
    rollout_eval_parser.add_argument("envelope_ref")
    rollout_accept_parser = worker_sub.add_parser("rollout-accept")
    rollout_accept_parser.add_argument("envelope_ref")
    rollout_accept_parser.add_argument("--accepted-by", required=True)
    rollout_accept_parser.add_argument("--now", required=True)

    task_parser = subparsers.add_parser("task")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)
    validate_parser = task_sub.add_parser("validate")
    validate_parser.add_argument("task_file", nargs="?")
    validate_parser.add_argument("--all-active", action="store_true")
    validate_parser.add_argument("--all-planned", action="store_true")
    promote_eval_parser = task_sub.add_parser("promote-eval")
    promote_eval_parser.add_argument("task_id")
    promote_eval_parser.add_argument("--omo-dir", default=".omo")
    promote_apply_parser = task_sub.add_parser("promote-apply")
    promote_apply_parser.add_argument("task_id")
    promote_apply_parser.add_argument("--promoted-by", required=True)
    promote_apply_parser.add_argument("--now", required=True)
    promote_apply_parser.add_argument("--omo-dir", default=".omo")
    promotion_history_parser = task_sub.add_parser("promotion-history")
    promotion_history_parser.add_argument("--omo-dir", default=".omo")
    promotion_history_parser.add_argument("--now")
    promotion_readiness_parser = task_sub.add_parser("promotion-readiness")
    promotion_readiness_parser.add_argument("--omo-dir", default=".omo")
    promotion_readiness_parser.add_argument("--now")
    promotion_request_parser = task_sub.add_parser("promotion-request-approval")
    promotion_request_parser.add_argument("task_id")
    promotion_request_parser.add_argument("--requested-by", required=True)
    promotion_request_parser.add_argument("--now", required=True)
    promotion_request_parser.add_argument("--omo-dir", default=".omo")
    contract_request_parser = task_sub.add_parser("contract-declare-deliverables")
    contract_request_parser.add_argument("task_id")
    contract_request_parser.add_argument("--deliverables", nargs="+", required=True)
    contract_request_parser.add_argument("--actor", required=True)
    contract_request_parser.add_argument("--now", required=True)
    contract_request_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_status_parser = task_sub.add_parser("promotion-approval-status")
    promotion_approval_status_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_status_parser.add_argument("--task-id")
    promotion_approval_status_parser.add_argument("--now")
    promotion_approval_history_parser = task_sub.add_parser(
        "promotion-approval-history"
    )
    promotion_approval_history_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_history_parser.add_argument("--now")
    promotion_approval_analytics_parser = task_sub.add_parser(
        "promotion-approval-analytics"
    )
    promotion_approval_analytics_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_analytics_parser.add_argument("--now")
    governance_overlay_status_parser = task_sub.add_parser("governance-overlay-status")
    governance_overlay_status_parser.add_argument("--omo-dir", default=".omo")
    governance_overlay_status_parser.add_argument("--now")
    governance_overlay_approval_prep_status_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-status"
    )
    governance_overlay_approval_prep_status_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_status_parser.add_argument("--now")
    governance_overlay_approval_prep_history_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-history"
    )
    governance_overlay_approval_prep_history_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_history_parser.add_argument("--now")
    governance_overlay_approval_prep_analytics_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-analytics"
    )
    governance_overlay_approval_prep_analytics_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_analytics_parser.add_argument("--now")
    governance_overlay_approval_prep_aging_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-aging"
    )
    governance_overlay_approval_prep_aging_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_aging_parser.add_argument("--now")
    governance_overlay_approval_prep_diff_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-diff"
    )
    governance_overlay_approval_prep_diff_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_diff_parser.add_argument("--now")
    governance_overlay_approval_prep_trend_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-trend"
    )
    governance_overlay_approval_prep_trend_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_trend_parser.add_argument("--now")
    governance_overlay_run_next_parser = task_sub.add_parser(
        "governance-overlay-run-next"
    )
    governance_overlay_run_next_parser.add_argument("--omo-dir", default=".omo")
    governance_overlay_run_next_parser.add_argument("--actor", required=True)
    governance_overlay_run_next_parser.add_argument("--now")

    args = parser.parse_args(argv)

    if args.command == "worker" and args.worker_command == "dispatch":
        dispatch_task(
            Path.cwd(),
            task_id=args.task_id,
            worker_id=args.worker_id,
            allowed_write_paths=args.write_paths,
            launch=args.launch,
            transport=args.transport,
            omo_dir=args.omo_dir,
        )
        return 0

    if args.command == "worker" and args.worker_command == "reclaim":
        reclaim_task(
            Path.cwd(),
            task_id=args.task_id,
            successor_worker_id=args.successor_worker_id,
            allowed_write_paths=args.write_paths,
            reason=args.reason,
            launch=args.launch,
            transport=args.transport,
            omo_dir=args.omo_dir,
        )
        return 0

    if args.command == "worker" and args.worker_command == "gc":
        return _worker_gc(
            Path.cwd(), dry_run=args.dry_run, retain=args.retain, omo_dir=args.omo_dir
        )

    if args.command == "worker" and args.worker_command == "status":
        return _print_worker_status(Path.cwd(), omo_dir=args.omo_dir)

    if args.command == "worker" and args.worker_command == "baseline":
        print(write_worker_utilization_summary(Path(args.root).resolve()))
        return 0

    if args.command == "worker" and args.worker_command == "handoff-index":
        print(write_handoff_index(Path.cwd(), args.task_id))
        return 0

    if args.command == "worker" and args.worker_command == "watchdog":
        return _print_worker_watchdog(Path.cwd(), now=args.now, omo_dir=args.omo_dir)

    if args.command == "worker" and args.worker_command == "admission-eval":
        return _print_worker_admission_eval(
            Path.cwd(), args.envelope_ref, matrix_ref=args.matrix_ref
        )

    if args.command == "worker" and args.worker_command == "admission-request-approval":
        return _request_worker_admission_approval(
            Path.cwd(), args.envelope_ref, requested_by=args.requested_by, now=args.now
        )

    if args.command == "worker" and args.worker_command == "rules-eval":
        return _print_worker_rules_eval(Path.cwd(), args.envelope_ref)

    if args.command == "worker" and args.worker_command == "rollout-eval":
        return _print_worker_rollout_eval(Path.cwd(), args.envelope_ref)

    if args.command == "worker" and args.worker_command == "rollout-accept":
        return _accept_worker_rollout(
            Path.cwd(), args.envelope_ref, accepted_by=args.accepted_by, now=args.now
        )

    if args.command == "task" and args.task_command == "validate":
        if args.all_planned:
            results = validate_planned_tasks(Path.cwd())
            if not results:
                return 0
            for path, errors in results.items():
                print(path)
                for error in errors:
                    print(f"  - {error}")
            return 1

        if args.all_active or not args.task_file:
            results = validate_active_tasks(Path.cwd())
            if not results:
                return 0
            for path, errors in results.items():
                print(path)
                for error in errors:
                    print(f"  - {error}")
            return 1

        errors = validate_task_file(Path(args.task_file))
        if not errors:
            return 0
        for error in errors:
            print(error)
        return 1

    if args.command == "task" and args.task_command == "promote-eval":
        return _print_task_promotion_eval(
            Path.cwd(), args.task_id, omo_dir=args.omo_dir
        )

    if args.command == "task" and args.task_command == "promote-apply":
        return _apply_task_promotion(
            Path.cwd(),
            args.task_id,
            promoted_by=args.promoted_by,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.command == "task" and args.task_command == "promotion-history":
        return _write_task_promotion_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "promotion-readiness":
        return _write_task_promotion_readiness(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "promotion-request-approval":
        return _request_task_promotion_approval(
            Path.cwd(),
            args.task_id,
            requested_by=args.requested_by,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.command == "task" and args.task_command == "contract-declare-deliverables":
        return _request_task_contract_declaration(
            Path.cwd(),
            args.task_id,
            deliverables=list(args.deliverables),
            actor=args.actor,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.command == "task" and args.task_command == "promotion-approval-status":
        return _write_task_promotion_approval_status(
            Path.cwd(),
            omo_dir=args.omo_dir,
            now=args.now,
            task_id=args.task_id,
        )

    if args.command == "task" and args.task_command == "promotion-approval-history":
        return _write_task_promotion_approval_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "promotion-approval-analytics":
        return _write_task_promotion_approval_analytics(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "governance-overlay-status":
        return _write_task_governance_overlay_status(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-status"
    ):
        return _write_task_governance_overlay_approval_prep_status(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-history"
    ):
        return _write_task_governance_overlay_approval_prep_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-analytics"
    ):
        return _write_task_governance_overlay_approval_prep_analytics(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-aging"
    ):
        return _write_task_governance_overlay_approval_prep_aging(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-diff"
    ):
        return _write_task_governance_overlay_approval_prep_diff(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-trend"
    ):
        return _write_task_governance_overlay_approval_prep_trend(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "governance-overlay-run-next":
        return _write_task_governance_overlay_run_next(
            Path.cwd(),
            omo_dir=args.omo_dir,
            actor=args.actor,
            now=args.now,
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
