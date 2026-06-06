#!/usr/bin/env python3
"""CLI for OMO cost tracking.

Usage:
  python3 scripts/omo_cost.py record --service agora --amount 10 --category compute --debt-id DEBT-OMO-004
  python3 scripts/omo_cost.py query [--limit 50]
  python3 scripts/omo_cost.py summary
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src/ to path so the package is importable from the repo root
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from omo.omo_cost import record_cost, query_costs, cost_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="omo-cost",
        description="OMO cost tracking CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # record subcommand
    record_parser = subparsers.add_parser("record", help="Record a cost entry")
    record_parser.add_argument("--service", required=True, help="Service name (e.g., agora, runtime)")
    record_parser.add_argument("--amount", type=float, required=True, help="Cost amount")
    record_parser.add_argument("--unit", default="credits", help="Cost unit (default: credits)")
    record_parser.add_argument("--category", default="compute", help="Cost category (compute, storage, maintenance, network)")
    record_parser.add_argument("--debt-id", default="", help="Associated debt item ID (optional)")
    record_parser.add_argument("--details", default="", help="Additional details (optional)")
    record_parser.add_argument("--cost-file", default="", help="Path to cost JSONL file (optional)")

    # query subcommand
    query_parser = subparsers.add_parser("query", help="Query recent cost entries")
    query_parser.add_argument("--limit", type=int, default=50, help="Number of entries to return (default: 50)")
    query_parser.add_argument("--cost-file", default="", help="Path to cost JSONL file (optional)")

    # summary subcommand
    summary_parser = subparsers.add_parser("summary", help="Show cost summary")
    summary_parser.add_argument("--cost-file", default="", help="Path to cost JSONL file (optional)")

    args = parser.parse_args()

    cost_file: str | Path | None = args.cost_file if args.cost_file else None

    if args.command == "record":
        entry = record_cost(
            service=args.service,
            amount=args.amount,
            unit=args.unit,
            category=args.category,
            debt_id=args.debt_id,
            details=args.details,
            cost_file=cost_file,
        )
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0

    if args.command == "query":
        records = query_costs(limit=args.limit, cost_file=cost_file)
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0

    if args.command == "summary":
        s = cost_summary(cost_file=cost_file)
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0

    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
