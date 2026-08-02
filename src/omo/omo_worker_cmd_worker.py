from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .omo_admission import evaluate_worker_envelope, request_conditional_approval
from .omo_handoff_index import write_handoff_index
from .omo_metrics import write_worker_utilization_summary
from .omo_rollout import accept_rollout_envelope, evaluate_rollout_envelope
from .omo_rules import evaluate_rule_bundle

# ── Extracted submodules ────────────────────────────────────────────────────
from .omo_worker_dispatch import (
    _worker_gc,
    dispatch_task,
    reclaim_task,
    yield_task,
)
from .omo_worker_status import (
    collect_worker_status,
    scan_runtime_watchdog,
)
from .worker_lifecycle import (
    acknowledge_worker,
    expire_worker_lease,
    reclaim_worker,
    renew_worker_lease,
)


def _mesh_lease_seconds() -> int:
    """Read the operator-configurable default lease without coupling it to a port rule."""
    raw = os.environ.get("OMO_MESH_LEASE_SECONDS", "1200")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("OMO_MESH_LEASE_SECONDS must be an integer") from exc
    if value <= 0:
        raise ValueError("OMO_MESH_LEASE_SECONDS must be positive")
    return value


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


def _print_mesh_event(event: dict[str, Any]) -> int:
    print(
        f"event_id={event['event_id']} event_type={event['event_type']} "
        f"workflow_run_id={event['workflow_run_id']}"
    )
    return 0


def _add_mesh_worker_context(parser: Any) -> None:
    parser.add_argument("workflow_run_id")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--dispatch-id", required=True)
    parser.add_argument("--worker", required=True, dest="worker_id")
    parser.add_argument("--step-run-id", required=True)
    parser.add_argument("--admission-id", required=True)
    parser.add_argument("--omo-dir", default=".omo")


def setup_worker_parser(subparsers: Any) -> None:
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

    mesh_ack_parser = worker_sub.add_parser("mesh-ack")
    _add_mesh_worker_context(mesh_ack_parser)
    mesh_ack_parser.add_argument(
        "--lease-seconds", type=int, default=_mesh_lease_seconds()
    )
    mesh_ack_parser.add_argument("--now")

    mesh_heartbeat_parser = worker_sub.add_parser("mesh-heartbeat")
    _add_mesh_worker_context(mesh_heartbeat_parser)
    mesh_heartbeat_parser.add_argument(
        "--lease-seconds", type=int, default=_mesh_lease_seconds()
    )
    mesh_heartbeat_parser.add_argument("--heartbeat-id")
    mesh_heartbeat_parser.add_argument("--now")

    mesh_expire_parser = worker_sub.add_parser("mesh-expire")
    _add_mesh_worker_context(mesh_expire_parser)
    mesh_expire_parser.add_argument("--reason", default="lease_expired")
    mesh_expire_parser.add_argument("--now")

    mesh_reclaim_parser = worker_sub.add_parser("mesh-reclaim")
    _add_mesh_worker_context(mesh_reclaim_parser)
    mesh_reclaim_parser.add_argument(
        "--successor-worker", required=True, dest="successor_worker_id"
    )
    mesh_reclaim_parser.add_argument(
        "--successor-dispatch", required=True, dest="successor_dispatch_id"
    )
    mesh_reclaim_parser.add_argument("--reason", default="lease_expired")
    mesh_reclaim_parser.add_argument("--now")

    yield_parser = worker_sub.add_parser("yield")
    yield_parser.add_argument("task_id")
    yield_parser.add_argument("--reason", required=True)
    yield_parser.add_argument("--omo-dir", default=".omo")

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


def execute_worker_command(args: argparse.Namespace) -> int:
    if args.worker_command == "dispatch":
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

    if args.worker_command == "reclaim":
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

    mesh_context = {
        "omo_dir": Path.cwd() / getattr(args, "omo_dir", ".omo"),
        "workflow_run_id": getattr(args, "workflow_run_id", None),
        "trace_id": getattr(args, "trace_id", None),
        "dispatch_id": getattr(args, "dispatch_id", None),
        "worker_id": getattr(args, "worker_id", None),
        "step_run_id": getattr(args, "step_run_id", None),
        "admission_id": getattr(args, "admission_id", None),
    }
    if args.worker_command == "mesh-ack":
        return _print_mesh_event(
            acknowledge_worker(
                **mesh_context,
                lease_seconds=args.lease_seconds,
                now=args.now,
            )
        )

    if args.worker_command == "mesh-heartbeat":
        return _print_mesh_event(
            renew_worker_lease(
                **mesh_context,
                lease_seconds=args.lease_seconds,
                heartbeat_id=args.heartbeat_id,
                now=args.now,
            )
        )

    if args.worker_command == "mesh-expire":
        return _print_mesh_event(
            expire_worker_lease(
                **mesh_context,
                reason=args.reason,
                now=args.now,
            )
        )

    if args.worker_command == "mesh-reclaim":
        return _print_mesh_event(
            reclaim_worker(
                **mesh_context,
                successor_worker_id=args.successor_worker_id,
                successor_dispatch_id=args.successor_dispatch_id,
                reason=args.reason,
                now=args.now,
            )
        )

    if args.worker_command == "yield":
        return yield_task(
            Path.cwd(),
            task_id=args.task_id,
            reason=args.reason,
            omo_dir=args.omo_dir,
        )

    if args.worker_command == "gc":
        return _worker_gc(
            Path.cwd(), dry_run=args.dry_run, retain=args.retain, omo_dir=args.omo_dir
        )

    if args.worker_command == "status":
        return _print_worker_status(Path.cwd(), omo_dir=args.omo_dir)

    if args.worker_command == "baseline":
        print(write_worker_utilization_summary(Path(args.root).resolve()))
        return 0

    if args.worker_command == "handoff-index":
        print(write_handoff_index(Path.cwd(), args.task_id))
        return 0

    if args.worker_command == "watchdog":
        return _print_worker_watchdog(Path.cwd(), now=args.now, omo_dir=args.omo_dir)

    if args.worker_command == "admission-eval":
        return _print_worker_admission_eval(
            Path.cwd(), args.envelope_ref, matrix_ref=args.matrix_ref
        )

    if args.worker_command == "admission-request-approval":
        return _request_worker_admission_approval(
            Path.cwd(), args.envelope_ref, requested_by=args.requested_by, now=args.now
        )

    if args.worker_command == "rules-eval":
        return _print_worker_rules_eval(Path.cwd(), args.envelope_ref)

    if args.worker_command == "rollout-eval":
        return _print_worker_rollout_eval(Path.cwd(), args.envelope_ref)

    if args.worker_command == "rollout-accept":
        return _accept_worker_rollout(
            Path.cwd(), args.envelope_ref, accepted_by=args.accepted_by, now=args.now
        )

    return 1
