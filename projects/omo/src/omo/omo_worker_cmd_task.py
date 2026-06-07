from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .omo_task_schema import (
    validate_active_tasks,
    validate_planned_tasks,
    validate_task_file,
)
from .omo_worker_promotion import (
    _print_task_promotion_eval,
    _apply_task_promotion,
    _request_task_promotion_approval,
    _request_task_contract_declaration,
    _write_task_promotion_history,
    _write_task_promotion_readiness,
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

def setup_task_parser(subparsers: Any) -> None:
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

def execute_task_command(args: argparse.Namespace) -> int:
    if args.task_command == "validate":
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

    if args.task_command == "promote-eval":
        return _print_task_promotion_eval(
            Path.cwd(), args.task_id, omo_dir=args.omo_dir
        )

    if args.task_command == "promote-apply":
        return _apply_task_promotion(
            Path.cwd(),
            args.task_id,
            promoted_by=args.promoted_by,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.task_command == "promotion-history":
        return _write_task_promotion_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "promotion-readiness":
        return _write_task_promotion_readiness(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "promotion-request-approval":
        return _request_task_promotion_approval(
            Path.cwd(),
            args.task_id,
            requested_by=args.requested_by,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.task_command == "contract-declare-deliverables":
        return _request_task_contract_declaration(
            Path.cwd(),
            args.task_id,
            deliverables=list(args.deliverables),
            actor=args.actor,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.task_command == "promotion-approval-status":
        return _write_task_promotion_approval_status(
            Path.cwd(),
            omo_dir=args.omo_dir,
            now=args.now,
            task_id=args.task_id,
        )

    if args.task_command == "promotion-approval-history":
        return _write_task_promotion_approval_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "promotion-approval-analytics":
        return _write_task_promotion_approval_analytics(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-status":
        return _write_task_governance_overlay_status(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-approval-prep-status":
        return _write_task_governance_overlay_approval_prep_status(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-approval-prep-history":
        return _write_task_governance_overlay_approval_prep_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-approval-prep-analytics":
        return _write_task_governance_overlay_approval_prep_analytics(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-approval-prep-aging":
        return _write_task_governance_overlay_approval_prep_aging(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-approval-prep-diff":
        return _write_task_governance_overlay_approval_prep_diff(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-approval-prep-trend":
        return _write_task_governance_overlay_approval_prep_trend(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.task_command == "governance-overlay-run-next":
        return _write_task_governance_overlay_run_next(
            Path.cwd(),
            omo_dir=args.omo_dir,
            actor=args.actor,
            now=args.now,
        )

    return 1
