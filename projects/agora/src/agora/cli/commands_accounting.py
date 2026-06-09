"""Accounting CLI commands: top, report, quota."""

from __future__ import annotations

from agora.accounting import DEFAULT_DAILY_QUOTA, ResourceAccountDB  # type: ignore[import-not-found]
from agora.cli.output import OutputFormatter


def cmd_accounting_top(args):
    """Show top callers by cost for a given period."""
    db = ResourceAccountDB()
    top = db.get_top_callers(period=args.period, limit=args.limit or 10)
    out = OutputFormatter(json_mode=getattr(args, "json", False))

    if not top:
        out.print_info(f"No accounting data found for period '{args.period}'.")
        return 0

    if args.json:
        out.print_json(top)
    else:
        rows = []
        for i, row in enumerate(top, 1):
            rows.append(
                [
                    str(i),
                    row["caller_id"],
                    f"{row['total_cost']:.6f}",
                    str(row["call_count"]),
                ]
            )
        out.print_table(
            ["#", "Caller", "Cost (USD)", "Calls"],
            rows,
            title=f"Top Callers (Period: {args.period})",
        )
    return 0


def cmd_accounting_report(args):
    """Show a summary report for a given period."""
    db = ResourceAccountDB()
    report = db.get_report(period=args.period)
    out = OutputFormatter(json_mode=getattr(args, "json", False))

    if args.json:
        out.print_json(report)
    else:
        summary_data = {
            "Total calls": report["total_calls"],
            "Total cost (USD)": f"{report['total_cost']:.6f}",
            "Unique callers": report["unique_callers"],
            "Avg cost/call": f"{report['avg_cost_per_call']:.6f}",
        }
        out.print_key_value(summary_data, f"Accounting Report (Period: {args.period})")

        if report["by_service"]:
            rows = [
                [
                    svc["service_name"],
                    str(svc["call_count"]),
                    f"{svc['total_cost']:.6f}",
                ]
                for svc in report["by_service"]
            ]
            out.print_table(
                ["Service", "Calls", "Cost (USD)"], rows, title="Breakdown by Service"
            )
    return 0


def cmd_accounting_quota(args):
    """Show quota usage for a caller."""
    db = ResourceAccountDB()
    quota_info = db.get_quota(args.caller)
    daily_quota = args.quota if args.quota is not None else DEFAULT_DAILY_QUOTA
    out = OutputFormatter(json_mode=getattr(args, "json", False))

    if args.json:
        out.print_json(
            {
                **quota_info,
                "daily_quota": daily_quota,
                "remaining": max(0.0, daily_quota - quota_info["today_cost"]),
            }
        )
    else:
        quota_data = {
            "Caller": quota_info["caller_id"],
            "Today cost": f"${quota_info['today_cost']:.6f}",
            "Total cost": f"${quota_info['total_cost']:.6f}",
            "Daily quota": f"${daily_quota:.2f}",
            "Remaining": f"${max(0.0, daily_quota - quota_info['today_cost']):.6f}",
        }
        out.print_key_value(quota_data, "Quota Report")

        if quota_info["today_cost"] >= daily_quota:
            out.print_warning("Daily quota exceeded!")
        elif quota_info["today_cost"] >= daily_quota * 0.8:
            out.print_warning("Approaching daily quota (80%+)")

    return 0
