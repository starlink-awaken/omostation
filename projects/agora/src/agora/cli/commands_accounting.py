"""Accounting CLI commands: top, report, quota."""

from __future__ import annotations

from agora.accounting import DEFAULT_DAILY_QUOTA, ResourceAccountDB  # type: ignore[import-not-found]


def cmd_accounting_top(args):
    """Show top callers by cost for a given period."""
    db = ResourceAccountDB()
    top = db.get_top_callers(period=args.period, limit=args.limit or 10)

    if not top:
        print(f"No accounting data found for period '{args.period}'.")
        return 0

    print(f"\n{'Top Callers':^60}")
    print(f"{'Period: ' + args.period:^60}")
    print("-" * 60)
    print(f"{'#':>3}  {'Caller':<24}  {'Cost (USD)':>12}  {'Calls':>8}")
    print("-" * 60)
    for i, row in enumerate(top, 1):
        print(f"{i:>3}  {row['caller_id']:<24}  {row['total_cost']:>12.6f}  {row['call_count']:>8}")
    print("-" * 60)
    return 0


def cmd_accounting_report(args):
    """Show a summary report for a given period."""
    db = ResourceAccountDB()
    report = db.get_report(period=args.period)

    print(f"\n{'Accounting Report':^60}")
    print(f"{'Period: ' + args.period:^60}")
    print("=" * 60)
    print(f"  Total calls:      {report['total_calls']}")
    print(f"  Total cost (USD): {report['total_cost']:.6f}")
    print(f"  Unique callers:   {report['unique_callers']}")
    print(f"  Avg cost/call:    {report['avg_cost_per_call']:.6f}")
    print("=" * 60)

    if report["by_service"]:
        print(f"\n{'Breakdown by Service':^50}")
        print("-" * 50)
        print(f"{'Service':<20}  {'Calls':>6}  {'Cost (USD)':>12}")
        print("-" * 50)
        for svc in report["by_service"]:
            print(f"{svc['service_name']:<20}  {svc['call_count']:>6}  {svc['total_cost']:>12.6f}")
        print("-" * 50)

    return 0


def cmd_accounting_quota(args):
    """Show quota usage for a caller."""
    db = ResourceAccountDB()
    quota_info = db.get_quota(args.caller)
    daily_quota = args.quota or DEFAULT_DAILY_QUOTA

    print(f"\n{'Quota Report':^50}")
    print("=" * 50)
    print(f"  Caller:      {quota_info['caller_id']}")
    print(f"  Today cost:  ${quota_info['today_cost']:.6f}")
    print(f"  Total cost:  ${quota_info['total_cost']:.6f}")
    print(f"  Daily quota: ${daily_quota:.2f}")
    print(f"  Remaining:   ${max(0.0, daily_quota - quota_info['today_cost']):.6f}")
    print("=" * 50)

    if quota_info["today_cost"] >= daily_quota:
        print("  ⚠️  Daily quota exceeded!")
    elif quota_info["today_cost"] >= daily_quota * 0.8:
        print("  ⚡  Approaching daily quota (80%+)")

    return 0
