#!/usr/bin/env python3
"""cost CLI — 资源消耗查询工具。

Usage:
    cost summary --today         当日消耗
    cost summary --week          本周消耗
    cost summary --month         本月消耗
    cost summary --by-service minerva.research_now  按服务过滤
    cost summary --by-caller agent:hermes            按调用者过滤
    cost estimate 1200           估算1200字符的token消耗
    cost estimate 1200 --service minerva.research_now

安装: ln -s ~/Workspace/kos/kos/accounting/cli.py ~/.local/bin/cost
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kos.accounting.db import COST_PER_1K, CostSummary, record_usage  # type: ignore[import-not-found]


def cmd_summary(args: argparse.Namespace) -> int:
    period = "today"
    if args.week:
        period = "week"
    elif args.month:
        period = "month"

    data = CostSummary.by_period(period)

    if args.by_service:
        data = {
            "period": period,
            "by_service": {
                args.by_service: data["by_service"].get(args.by_service, {"tokens": 0, "cost": 0, "calls": 0})
            },
        }

    if args.by_caller:
        data = {
            "period": period,
            "by_caller": {args.by_caller: data["by_caller"].get(args.by_caller, {"tokens": 0, "cost": 0, "calls": 0})},
        }

    if args.json:
        import json

        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(f"# 资源消耗 — {period}")
    print("总消耗: $" + f"{data['total_cost_usd']:.4f} ({data['total_tokens']:,} tokens, {data['total_calls']} calls)")
    print()
    print("## 按服务")
    for svc, info in data.get("by_service", {}).items():
        print("  " + svc + " " * max(1, 35 - len(svc)) + f"{info['tokens']:>8,} tokens  ${info['cost']:.4f}")
    print()
    print("## 按调用者")
    for clr, info in data.get("by_caller", {}).items():
        print(f"  {clr:<35s} {info['tokens']:>8,} tokens  ${info['cost']:.4f}")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    result = CostSummary.estimate(args.text_length, args.service or "default")
    print(f"估计tokens: {result['estimated_tokens']:,}")
    print(f"估计成本:   ${result['estimated_cost_usd']:.6f}")
    print(f"服务:       {result['service']}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    call_id = record_usage(
        caller=args.caller,
        service=args.service,
        tokens_input=args.tokens_input or 0,
        tokens_output=args.tokens_output or 0,
    )
    print(call_id)
    return 0


def cmd_services(_args: argparse.Namespace) -> int:
    print("已注册服务单价 (USD/1K tokens):")
    for svc in sorted(COST_PER_1K):
        rates = COST_PER_1K[svc]
        if svc == "default":
            continue
        print(f"  {svc:<40s} in=${rates['input']:.4f} out=${rates['output']:.4f}")
    return 0


def main() -> int:
    print("⚠️ KOS Accounting 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    parser = argparse.ArgumentParser(description="KOS 资源消耗追踪")
    sub = parser.add_subparsers(dest="command")

    summary_p = sub.add_parser("summary", help="查看消耗汇总")
    summary_p.add_argument("--today", action="store_true", default=True)
    summary_p.add_argument("--week", action="store_true")
    summary_p.add_argument("--month", action="store_true")
    summary_p.add_argument("--by-service", type=str)
    summary_p.add_argument("--by-caller", type=str)
    summary_p.add_argument("--json", action="store_true")

    est_p = sub.add_parser("estimate", help="估算token消耗")
    est_p.add_argument("text_length", type=int, help="文本字符数")
    est_p.add_argument("--service", type=str)

    record_p = sub.add_parser("record", help="记录一次消耗")
    record_p.add_argument("--caller", required=True)
    record_p.add_argument("--service", required=True)
    record_p.add_argument("--tokens-input", type=int)
    record_p.add_argument("--tokens-output", type=int)

    sub.add_parser("services", help="列出已注册服务单价")

    args = parser.parse_args()
    if args.command == "summary":
        return cmd_summary(args)
    elif args.command == "estimate":
        return cmd_estimate(args)
    elif args.command == "record":
        return cmd_record(args)
    elif args.command == "services":
        return cmd_services(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
