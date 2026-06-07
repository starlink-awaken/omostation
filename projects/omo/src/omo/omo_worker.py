#!/usr/bin/env python3
from __future__ import annotations

import argparse

# Re-export facade imports for backward compatibility
from .omo_admission import evaluate_worker_envelope, request_conditional_approval
from .omo_handoff_index import write_handoff_index
from .omo_metrics import write_worker_utilization_summary
from .omo_rules import evaluate_rule_bundle
from .omo_rollout import accept_rollout_envelope, evaluate_rollout_envelope
from .omo_task_schema import (
    validate_active_tasks,
    validate_planned_tasks,
    validate_task_file,
)
from .omo_worker_status import (
    collect_worker_status,
    scan_runtime_watchdog,
)
from .omo_worker_dispatch import (
    dispatch_task,
    reclaim_task,
    _worker_gc,
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

from .omo_worker_cmd_worker import setup_worker_parser, execute_worker_command
from .omo_worker_cmd_task import setup_task_parser, execute_task_command

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_worker_parser(subparsers)
    setup_task_parser(subparsers)

    args = parser.parse_args(argv)

    if args.command == "worker":
        return execute_worker_command(args)
    if args.command == "task":
        return execute_task_command(args)

    return 1

if __name__ == "__main__":
    raise SystemExit(main())
