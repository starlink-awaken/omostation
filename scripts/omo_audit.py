#!/usr/bin/env python3
"""CLI for governance audit trail.

Usage:
  python3 scripts/omo_audit.py record --action close --debt-id DEBT-OMO-004 --actor omo-agent
  python3 scripts/omo_audit.py query [--limit 50]
  python3 scripts/omo_audit.py summary
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

from omo.omo_audit import record, query, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="omo-audit",
        description="OMO governance audit trail CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # record subcommand
    record_parser = subparsers.add_parser("record", help="Record a governance action")
    record_parser.add_argument("--action", required=True, help="Action name (e.g., close, reopen, escalate)")
    record_parser.add_argument("--debt-id", default="", help="Debt item ID (optional)")
    record_parser.add_argument("--actor", default="", help="Who performed the action (optional)")
    record_parser.add_argument("--details", default="", help="Additional details (optional)")
    record_parser.add_argument("--audit-file", default="", help="Path to audit JSONL file (optional)")

    # query subcommand
    query_parser = subparsers.add_parser("query", help="Query recent audit records")
    query_parser.add_argument("--limit", type=int, default=50, help="Number of records to return (default: 50)")
    query_parser.add_argument("--audit-file", default="", help="Path to audit JSONL file (optional)")

    # summary subcommand
    summary_parser = subparsers.add_parser("summary", help="Show audit summary")
    summary_parser.add_argument("--audit-file", default="", help="Path to audit JSONL file (optional)")

    args = parser.parse_args()

    audit_file: str | Path | None = args.audit_file if args.audit_file else None

    if args.command == "record":
        entry = record(
            action=args.action,
            debt_id=args.debt_id,
            actor=args.actor,
            details=args.details,
            audit_file=audit_file,
        )
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0

    if args.command == "query":
        records = query(limit=args.limit, audit_file=audit_file)
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0

    if args.command == "summary":
        s = summary(audit_file=audit_file)
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0

    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
