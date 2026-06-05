#!/usr/bin/env python3
"""OMO observability CLI — log search, tail, and metric inspection.

All commands read from existing JSONL/YAML files (KEI audit, execution logs,
TaskObject envelopes). No new data sources created.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_DATA = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data"


def _kei_audit_path() -> Path:
    return RUNTIME_DATA / "kei_audit.jsonl"


def _execution_log_path() -> Path:
    return Path(os.environ.get("EXECUTION_LOG",
        str(Path.home() / "Workspace" / "projects" / "kairon" / "packages" / "agent-runtime" / "src" / "agent_runtime" / "execution_log.jsonl")))


def _taskobject_log_path() -> Path:
    return RUNTIME_DATA.parent / "taskobject_envelopes.jsonl"


def _read_jsonl(path: Path, max_lines: int = 0) -> list[dict]:
    """Read JSONL file, return list of dicts. max_lines=0 means all."""
    if not path.exists():
        return []
    lines = path.read_text().strip().split("\n")
    if max_lines > 0:
        lines = lines[-max_lines:]
    results = []
    for line in lines:
        if line.strip():
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                results.append({"raw": line[:200]})
    return results


def cmd_log_search(
    log_type: str,
    keyword: str | None,
    status: str | None,
    since: str | None,
    limit: int,
) -> int:
    """Search log files for matching records."""
    path_map = {
        "kei": _kei_audit_path(),
        "execution": _execution_log_path(),
        "taskobject": _taskobject_log_path(),
    }
    path = path_map.get(log_type)
    if not path:
        print(f"❌ Unknown log type: {log_type} (use: kei, execution, taskobject)", file=sys.stderr)
        return 1
    records = _read_jsonl(path)
    if not records:
        print(f"ℹ️  No records in {path.name}")
        return 0

    filtered = records
    if keyword:
        filtered = [r for r in filtered if keyword.lower() in json.dumps(r).lower()]
    if status:
        filtered = [r for r in filtered if r.get("status") == status]
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            filtered = [
                r for r in filtered
                if "ts" in r and datetime.fromisoformat(r["ts"]) >= since_dt
            ]
        except ValueError:
            pass  # ignore bad date format

    filtered = filtered[:limit]
    print(f"Found {len(filtered)} records (of {len(records)} total)")
    print()
    for r in filtered:
        ts = r.get("ts", r.get("timestamp", "?"))
        action = r.get("action", r.get("status", "?"))
        detail = r.get("details", r.get("result", ""))[:80]
        ext = r.get("extension_id", "")
        print(f"  [{ts}] {action:12s} {ext:30s} {detail}")
    return 0


def cmd_log_tail(log_type: str, lines: int) -> int:
    """Tail last N lines of a log file."""
    path_map = {
        "kei": _kei_audit_path(),
        "execution": _execution_log_path(),
        "taskobject": _taskobject_log_path(),
    }
    path = path_map.get(log_type)
    if not path:
        print(f"❌ Unknown log type: {log_type}", file=sys.stderr)
        return 1
    records = _read_jsonl(path, max_lines=lines)
    if not records:
        print(f"ℹ️  No records in {path.name}")
        return 0
    print(f"Last {len(records)} records from {path.name}:")
    print()
    for r in records:
        ts = r.get("ts", r.get("timestamp", "?"))
        action = r.get("action", r.get("status", "?"))
        detail = r.get("details", r.get("error", ""))[:100]
        print(f"  [{ts}] {action}: {detail}")
    return 0


def cmd_log_stats(log_type: str) -> int:
    """Show log file statistics."""
    path_map = {
        "kei": _kei_audit_path(),
        "execution": _execution_log_path(),
        "taskobject": _taskobject_log_path(),
    }
    path = path_map.get(log_type)
    if not path:
        print(f"❌ Unknown log type: {log_type}", file=sys.stderr)
        return 1
    records = _read_jsonl(path)
    total = len(records)
    if total == 0:
        print(f"ℹ️  {path.name}: empty")
        return 0
    file_size = path.stat().st_size
    statuses: dict[str, int] = {}
    actions: dict[str, int] = {}
    for r in records:
        s = r.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
        a = r.get("action", "unknown")
        actions[a] = actions.get(a, 0) + 1
    print(f"File:     {path.name}")
    print(f"Size:     {file_size:,} bytes")
    print(f"Records:  {total}")
    if statuses:
        print(f"\nBy status:")
        for s, c in sorted(statuses.items()):
            print(f"  {s}: {c}")
    if actions:
        print(f"\nBy action:")
        for a, c in sorted(actions.items()):
            print(f"  {a}: {c}")
    return 0


def cmd_metric_show() -> int:
    """Show _STATS counters from runtime MCP server (runtime state)."""
    # _STATS is in the runtime MCP server's module state — query via KEI audit
    kei_records = _read_jsonl(_kei_audit_path())
    tool_calls: dict[str, int] = {}
    for r in kei_records:
        ext = r.get("extension_id", "")
        if ext and "tool" in ext.lower():
            tool_calls[ext] = tool_calls.get(ext, 0) + 1
    total = len(kei_records)
    calls = sum(tool_calls.values())
    print(f"KEI Audit Total:  {total}")
    print(f"Tool Calls:       {calls}")
    print()
    if tool_calls:
        print("By extension:")
        for ext, count in sorted(tool_calls.items(), key=lambda x: -x[1])[:15]:
            print(f"  {ext:40s} {count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo observability", description="OMO log/metric inspection")
    sub = parser.add_subparsers(dest="command")

    # log search
    ls = sub.add_parser("log", help="Search and inspect logs")
    ls_sub = ls.add_subparsers(dest="log_cmd")
    ls_search = ls_sub.add_parser("search", help="Search logs")
    ls_search.add_argument("--type", "-t", choices=["kei", "execution", "taskobject"], default="kei")
    ls_search.add_argument("--keyword", "-k", help="Keyword to search for")
    ls_search.add_argument("--status", "-s", help="Filter by status (pass/fail/error)")
    ls_search.add_argument("--since", help="ISO datetime filter (e.g. 2026-06-01)")
    ls_search.add_argument("--limit", "-n", type=int, default=20)

    ls_tail = ls_sub.add_parser("tail", help="Tail last N records")
    ls_tail.add_argument("--type", "-t", choices=["kei", "execution", "taskobject"], default="kei")
    ls_tail.add_argument("--lines", "-n", type=int, default=10)

    ls_stats = ls_sub.add_parser("stats", help="Log file statistics")
    ls_stats.add_argument("--type", "-t", choices=["kei", "execution", "taskobject"], default="kei")

    # metric
    sub.add_parser("metric", help="Show aggregated metrics")

    args = parser.parse_args(argv)
    if args.command == "log":
        if args.log_cmd == "search":
            return cmd_log_search(args.type, args.keyword, args.status, args.since, args.limit)
        elif args.log_cmd == "tail":
            return cmd_log_tail(args.type, args.lines)
        elif args.log_cmd == "stats":
            return cmd_log_stats(args.type)
        else:
            ls.print_help()
            return 1
    elif args.command == "metric":
        return cmd_metric_show()
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
