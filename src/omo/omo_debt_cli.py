"""omo_debt_cli — omo-debt CLI argparse + main() (P110 split from omo_debt.py).

P110 refactor: omo_debt.py 1085L → split off ~315L CLI 入口.
- omo_debt.py: business functions (write_dashboard / write_*_packet / helpers)
- omo_debt_cli.py: argparse setup + main() dispatcher
- omo-debt CLI 调用方不变 (入口 main() 行为一致).

P110 关联: TASK-F7114ABA (omo lint god-module 硬规则 800L, omo_debt 1085L
触发 lint-error 负债清单, 需治本拆分).
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import yaml


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def cmd_debt_list(omo_dir: Path) -> int:
    """List debt items from state/system.yaml."""
    system_path = omo_dir / "state" / "system.yaml"
    if not system_path.exists():
        print("No debt state found.")
        return 0

    docs = list(yaml.safe_load_all(system_path.read_text(encoding="utf-8")))
    system = {}
    for doc in docs:
        if isinstance(doc, dict):
            system.update(doc)

    items = system.get("debt_weight_items", {})
    # resolved 标记集 (显示用): resolved_debt_items 历史 + items 内 resolved=True
    resolved_display = set(system.get("resolved_debt_items", []))
    # 计数集: 仅基于 debt_weight_items, 避免 resolved_debt_items 含外部历史项
    # 导致 open_count = total - resolved 出现负数 (P71 SSOT 口径不一致副作用)
    resolved_in_items = {
        debt_id
        for debt_id, info in items.items()
        if isinstance(info, dict) and info.get("resolved")
    }
    resolved_display.update(resolved_in_items)
    total = len(items)
    resolved_count = len(resolved_in_items)
    open_count = total - resolved_count

    print(f"{total} total: {open_count} open / {resolved_count} resolved")
    for debt_id, info in items.items():
        status = "resolved" if debt_id in resolved_display else "open"
        desc = info.get("desc", "") if isinstance(info, dict) else ""
        print(f"  {debt_id} [{status}] {desc}")
    return 0


def cmd_debt_close(
    omo_dir: Path,
    debt_id: str,
    *,
    dry_run: bool = False,
    confirm: bool = True,
    actor: str = "",
) -> int:
    """Close a canonical debt item."""
    from omo.omo_debt import _load_yaml, _write_yaml
    from omo.omo_debt_lifecycle import append_history, update_item

    item_path, payload = update_item(omo_dir, debt_id, _load_yaml)
    if not item_path.exists():
        print(f"❌ 未知 debt_id: {debt_id} (不在 .omo/debt/items)")
        return 1

    payload["lifecycle_state"] = "closed"
    payload["gate_level"] = "none"
    payload["closed_at"] = _now_iso()
    # 治本: 剥离越权的 legacy `status` 字段 (yaml-bypass lint 期望 lifecycle_state 唯一)
    if "status" in payload:
        payload.pop("status")
    append_history(
        payload,
        "close",
        "Closed debt item.",
        actor=actor,
        timestamp=_now_iso(),
    )
    if dry_run:
        print(f"[dry-run] would close {debt_id}")
        return 0

    if not confirm:
        print("❌ 请显式传入 confirm=True 以关闭债务项")
        return 1

    _write_yaml(item_path, payload)
    print(f"closed {debt_id} (债务项已关闭)")
    return 0


def cmd_debt_desc(
    omo_dir: Path,
    debt_id: str,
    description: str,
    *,
    dry_run: bool = False,
    actor: str = "",
) -> int:
    """Update the description of a canonical debt item."""
    from omo.omo_debt import _load_yaml, _write_yaml
    from omo.omo_debt_lifecycle import append_history, update_item

    item_path, payload = update_item(omo_dir, debt_id, _load_yaml)
    if not item_path.exists():
        print(f"❌ 未知 debt_id: {debt_id} (不在 .omo/debt/items)")
        return 1

    old_desc = payload.get("description", "")
    payload["description"] = description
    append_history(
        payload,
        "update_description",
        f"Updated description from '{old_desc}' to '{description}'.",
        actor=actor,
        timestamp=_now_iso(),
    )
    if dry_run:
        print(f"[dry-run] would update description for {debt_id}")
        return 0
    _write_yaml(item_path, payload)
    print(f"{debt_id} description 已更新")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 入口. 业务函数从 omo_debt 惰性导入 (避免循环)."""
    # 业务函数 imports (移到这里避免 omo_debt 顶层 re-export 时的循环)
    from omo.omo_debt import (
        _load_yaml,
        _positive_int,
        _write_yaml,
        approve_item,
        campaign_outputs,
        dispatch_outputs,
        refresh_outputs,
        reporting_diff_outputs,
        reporting_history_outputs,
        reporting_outputs,
        reporting_trend_outputs,
        require_dispatch_bound_revalidate,
        require_matching_revalidate_approval,
    )
    from omo.omo_debt_execution import build_execution_record, execution_record_path
    from omo.omo_debt_lifecycle import (
        append_history,
        append_registry_ref,
        register_item,
        schedule_item,
        update_item,
    )

    parser = argparse.ArgumentParser(prog="omo-debt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--omo-dir", default=".omo")
    register_parser.add_argument("--id", required=True)
    register_parser.add_argument("--title", required=True)
    register_parser.add_argument("--dimension", required=True)
    register_parser.add_argument("--subdimension", required=True)
    register_parser.add_argument("--severity", required=True)
    register_parser.add_argument("--owner", required=True)
    register_parser.add_argument(
        "--actor", default="", help="Who performed this action (default: empty)"
    )
    register_parser.add_argument(
        "--x1-policy-ref", default="", help="X1 governance policy reference ID"
    )
    register_parser.add_argument(
        "--x2-freshness", default="", help="X2 freshness timestamp (ISO 8601)"
    )
    register_parser.add_argument(
        "--x3-tier",
        default="",
        help="X3 value tier (Axiom/Principle/Theory/Framework/Knowledge/Skill/Tool)",
    )

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--omo-dir", default=".omo")

    schedule_parser = subparsers.add_parser("schedule")
    schedule_parser.add_argument("--omo-dir", default=".omo")
    schedule_parser.add_argument("--id", required=True)
    schedule_parser.add_argument("--next-review-at", required=True)

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("--omo-dir", default=".omo")
    refresh_parser.add_argument("--now", required=True)

    dispatch_parser = subparsers.add_parser("dispatch")
    dispatch_parser.add_argument("--omo-dir", default=".omo")
    dispatch_parser.add_argument("--now", required=True)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--omo-dir", default=".omo")
    approve_parser.add_argument("--id", required=True)
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--scope", required=True)
    approve_parser.add_argument("--approved-at", required=True)

    campaign_parser = subparsers.add_parser("campaign")
    campaign_parser.add_argument("--omo-dir", default=".omo")
    campaign_parser.add_argument("--run-ref")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--omo-dir", default=".omo")
    report_parser.add_argument("--run-ref")

    report_history_parser = subparsers.add_parser("report-history")
    report_history_parser.add_argument("--omo-dir", default=".omo")

    report_diff_parser = subparsers.add_parser("report-diff")
    report_diff_parser.add_argument("--omo-dir", default=".omo")

    report_trend_parser = subparsers.add_parser("report-trend")
    report_trend_parser.add_argument("--omo-dir", default=".omo")
    report_trend_parser.add_argument("--last", type=_positive_int)
    report_trend_parser.add_argument("--from-run-stamp")
    report_trend_parser.add_argument("--to-run-stamp")

    reclassify_parser = subparsers.add_parser("reclassify")
    reclassify_parser.add_argument("--omo-dir", default=".omo")
    reclassify_parser.add_argument("--id", required=True)
    reclassify_parser.add_argument("--dimension", required=True)
    reclassify_parser.add_argument("--subdimension", required=True)

    escalate_parser = subparsers.add_parser("escalate")
    escalate_parser.add_argument("--omo-dir", default=".omo")
    escalate_parser.add_argument("--id", required=True)
    escalate_parser.add_argument("--gate-level", required=True)

    revalidate_parser = subparsers.add_parser("revalidate")
    revalidate_parser.add_argument("--omo-dir", default=".omo")
    revalidate_parser.add_argument("--id", required=True)
    revalidate_parser.add_argument("--reviewed-at", required=True)
    revalidate_parser.add_argument("--dispatch-run-ref")

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--omo-dir", default=".omo")
    close_parser.add_argument("--id", required=True)
    close_parser.add_argument("--actor", default="", help="Who performed this action")
    close_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing",
    )
    close_parser.add_argument(
        "--no-confirm",
        dest="confirm",
        action="store_false",
        default=True,
        help="Refuse to close without this safety flag (default: confirm)",
    )

    desc_parser = subparsers.add_parser("desc")
    desc_parser.add_argument("--omo-dir", default=".omo")
    desc_parser.add_argument("--id", required=True)
    desc_parser.add_argument("--description", required=True)
    desc_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing",
    )

    reopen_parser = subparsers.add_parser("reopen")
    reopen_parser.add_argument("--omo-dir", default=".omo")
    reopen_parser.add_argument("--id", required=True)
    reopen_parser.add_argument("--actor", default="", help="Who performed this action")

    args = parser.parse_args(argv)
    omo_dir = Path(args.omo_dir)

    if args.command == "register":
        timestamp = _now_iso()
        payload = register_item(args, timestamp=timestamp)
        item_ref = f".omo/debt/items/{args.id}.yaml"
        item_path = omo_dir / "debt" / "items" / f"{args.id}.yaml"
        _write_yaml(item_path, payload)
        append_registry_ref(omo_dir, item_ref)  # type: ignore[reportCallIssue]
        print(f"registered {args.id}")
        return 0

    if args.command == "list":
        return cmd_debt_list(omo_dir)

    if args.command == "schedule":
        schedule_item(
            omo_dir,
            args.id,
            args.next_review_at,
            _load_yaml,
            _write_yaml,
            _now_iso(),
        )
        print(f"scheduled {args.id}")
        return 0

    if args.command == "refresh":
        refresh_outputs(omo_dir, args.now)
        print("refreshed debt outputs")
        return 0

    if args.command == "dispatch":
        dispatch_outputs(omo_dir, args.now)
        print("dispatched debt outputs")
        return 0

    if args.command == "approve":
        approve_item(
            omo_dir,
            args.id,
            args.approved_by,
            args.scope,
            args.approved_at,
        )
        print(f"approved {args.id} ({args.scope})")
        return 0

    if args.command == "campaign":
        campaign_outputs(omo_dir, args.run_ref)
        print(f"campaigned {args.run_ref or 'latest'}")
        return 0

    if args.command == "report":
        reporting_outputs(omo_dir, args.run_ref)
        print(f"reported {args.run_ref or 'latest'}")
        return 0

    if args.command == "report-history":
        reporting_history_outputs(omo_dir)
        print("reported history")
        return 0

    if args.command == "report-diff":
        reporting_diff_outputs(omo_dir)
        print("reported diff")
        return 0

    if args.command == "report-trend":
        reporting_trend_outputs(
            omo_dir, args.last, args.from_run_stamp, args.to_run_stamp
        )
        print("reported trend")
        return 0

    if args.command == "reclassify":
        item_path, payload = update_item(omo_dir, args.id, _load_yaml)
        payload["dimension"] = args.dimension
        payload["subdimension"] = args.subdimension
        append_history(
            payload,
            "reclassify",
            f"Reclassified to {args.dimension}/{args.subdimension}.",
        )
        _write_yaml(item_path, payload)
        print(f"reclassified {args.id}")
        return 0

    if args.command == "escalate":
        item_path, payload = update_item(omo_dir, args.id, _load_yaml)
        payload["gate_level"] = args.gate_level
        append_history(payload, "escalate", f"Escalated to {args.gate_level}.")
        _write_yaml(item_path, payload)
        print(f"escalated {args.id}")
        return 0

    if args.command == "revalidate":
        bound_run_ref = require_dispatch_bound_revalidate(
            omo_dir, args.id, args.dispatch_run_ref
        )
        require_matching_revalidate_approval(omo_dir, args.id, bound_run_ref)
        item_path, payload = update_item(omo_dir, args.id, _load_yaml)
        payload["last_reviewed_at"] = args.reviewed_at
        append_history(payload, "revalidate", f"Reviewed at {args.reviewed_at}.")
        _write_yaml(item_path, payload)
        if bound_run_ref:
            record_path = execution_record_path(omo_dir, bound_run_ref, args.id)
            if record_path.exists():
                raise FileExistsError(f"execution record already exists: {record_path}")
            _write_yaml(
                record_path,
                build_execution_record(
                    item_id=args.id,
                    dispatch_run_ref=bound_run_ref,
                    reviewed_at=args.reviewed_at,
                ),
            )
        print(f"revalidated {args.id}")
        return 0

    if args.command == "close":
        return cmd_debt_close(
            omo_dir,
            args.id,
            dry_run=args.dry_run,
            confirm=args.confirm,
            actor=getattr(args, "actor", ""),
        )

    if args.command == "desc":
        return cmd_debt_desc(
            omo_dir,
            args.id,
            args.description,
            dry_run=args.dry_run,
        )

    if args.command == "reopen":
        item_path, payload = update_item(omo_dir, args.id, _load_yaml)
        payload["lifecycle_state"] = "identified"
        append_history(
            payload,
            "reopen",
            "Reopened debt item.",
            actor=getattr(args, "actor", ""),
            timestamp=_now_iso(),
        )
        _write_yaml(item_path, payload)
        print(f"reopened {args.id}")
        return 0

    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
