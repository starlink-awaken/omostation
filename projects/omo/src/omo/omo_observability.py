#!/usr/bin/env python3
"""OMO observability CLI — log search, tail, and metric inspection.

All commands read from existing JSONL/YAML files (KEI audit, execution logs,
TaskObject envelopes, .omo/_knowledge/*.jsonl). No new data sources created.

Round 4 (P1-1): 新增 ``knowledge`` log type, 支持 .omo/_knowledge/ 多文件
tail/search/stats. 落点: bos-metrics, omo-sync, governance-history 等 AppendOnlyLog
consumer 的输出都自动可查.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


RUNTIME_DATA = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data"

# Round 4: .omo/_knowledge/ 是 AppendOnlyLog 消费者的落点目录
_WORKSPACE = Path(
    os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
)
KNOWLEDGE_DIR = _WORKSPACE / ".omo" / "_knowledge"


def _kei_audit_path() -> Path:
    return RUNTIME_DATA / "kei_audit.jsonl"


def _execution_log_path() -> Path:
    return Path(os.environ.get("EXECUTION_LOG",
        str(Path.home() / "Workspace" / "projects" / "kairon" / "packages" / "agent-runtime" / "src" / "agent_runtime" / "execution_log.jsonl")))


def _taskobject_log_path() -> Path:
    return RUNTIME_DATA.parent / "taskobject_envelopes.jsonl"


def _knowledge_log_paths() -> list[Path]:
    """List all .jsonl files in .omo/_knowledge/ (sorted by mtime, newest first)."""
    if not KNOWLEDGE_DIR.exists():
        return []
    return sorted(
        (p for p in KNOWLEDGE_DIR.glob("*.jsonl") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


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


def _resolve_log_paths(log_type: str, file_filter: str | None) -> list[Path]:
    """Resolve log type + optional --file filter to list of paths."""
    if log_type == "knowledge":
        all_paths = _knowledge_log_paths()
        if file_filter:
            # 支持完整文件名 (bos-metrics.jsonl) 或仅 stem (bos-metrics)
            return [p for p in all_paths if p.name == file_filter or p.stem == file_filter]
        return all_paths
    path_map = {
        "kei": _kei_audit_path(),
        "execution": _execution_log_path(),
        "taskobject": _taskobject_log_path(),
    }
    path = path_map.get(log_type)
    if path is None:
        return []
    return [path]


def cmd_log_search(
    log_type: str,
    keyword: str | None,
    status: str | None,
    since: str | None,
    limit: int,
    file_filter: str | None = None,
) -> int:
    """Search log files for matching records."""
    paths = _resolve_log_paths(log_type, file_filter)
    if not paths:
        print(
            f"❌ Unknown log type: {log_type} (use: kei, execution, taskobject, knowledge)",
            file=sys.stderr,
        )
        return 1

    # 聚合所有 path 的 records (knowledge 多文件场景)
    all_records: list[dict] = []
    for p in paths:
        for r in _read_jsonl(p):
            r["_source_file"] = p.name
            all_records.append(r)
    if not all_records:
        print(f"ℹ️  No records in {len(paths)} file(s)")
        return 0

    filtered = all_records
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
            pass

    filtered = filtered[:limit]
    print(f"Found {len(filtered)} records (of {len(all_records)} total, across {len(paths)} file(s))")
    print()
    for r in filtered:
        ts = r.get("ts", r.get("timestamp", r.get("recorded_at", "?")))
        action = r.get("action", r.get("status", r.get("kind", "?")))
        detail = r.get("details", r.get("result", r.get("error", "")))[:80]
        ext = r.get("extension_id", "")
        src = r.get("_source_file", "")
        print(f"  [{ts}] {action:12s} {ext:30s} {detail}  ({src})")
    return 0


def cmd_log_tail(log_type: str, lines: int, file_filter: str | None = None) -> int:
    """Tail last N lines of a log file (or all .jsonl in .omo/_knowledge/ for knowledge type)."""
    paths = _resolve_log_paths(log_type, file_filter)
    if not paths:
        print(
            f"❌ Unknown log type: {log_type} (use: kei, execution, taskobject, knowledge)",
            file=sys.stderr,
        )
        return 1

    # knowledge 多文件: 每文件取最后 N 条, 全部按 mtime 排序
    all_records: list[dict] = []
    for p in paths:
        for r in _read_jsonl(p, max_lines=lines):
            r["_source_file"] = p.name
            all_records.append(r)
    if not all_records:
        print(f"ℹ️  No records in {len(paths)} file(s)")
        return 0

    # 按 ts 排序 (knowledge 混合文件时)
    if log_type == "knowledge":
        all_records.sort(key=lambda r: r.get("ts", r.get("recorded_at", "")), reverse=True)
        all_records = all_records[:lines]

    if log_type == "knowledge" and len(paths) > 1:
        print(f"Last {len(all_records)} records from {len(paths)} .jsonl files in .omo/_knowledge/:")
    else:
        print(f"Last {len(all_records)} records from {paths[0].name}:")
    print()
    for r in all_records:
        ts = r.get("ts", r.get("recorded_at", "?"))
        action = r.get("action", r.get("status", r.get("kind", "?")))
        detail = r.get("details", r.get("error", ""))[:100]
        src = r.get("_source_file", "")
        if log_type == "knowledge" and len(paths) > 1:
            print(f"  [{ts}] {action}: {detail}  ({src})")
        else:
            print(f"  [{ts}] {action}: {detail}")
    return 0


def cmd_log_stats(log_type: str, file_filter: str | None = None) -> int:
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
        print("\nBy status:")
        for s, c in sorted(statuses.items()):
            print(f"  {s}: {c}")
    if actions:
        print("\nBy action:")
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

    # Round 4: knowledge log type 支持多文件 (.omo/_knowledge/*.jsonl)
    # sub.add_argument choices 加入 "knowledge", ls_tail 加 --file 过滤
    _log_types = ["kei", "execution", "taskobject", "knowledge"]

    # log search
    ls = sub.add_parser("log", help="Search and inspect logs")
    ls_sub = ls.add_subparsers(dest="log_cmd")
    ls_search = ls_sub.add_parser("search", help="Search logs")
    ls_search.add_argument("--type", "-t", choices=_log_types, default="kei")
    ls_search.add_argument("--keyword", "-k", help="Keyword to search for")
    ls_search.add_argument("--status", "-s", help="Filter by status (pass/fail/error)")
    ls_search.add_argument("--since", help="ISO datetime filter (e.g. 2026-06-01)")
    ls_search.add_argument("--limit", "-n", type=int, default=20)
    ls_search.add_argument(
        "--file",
        help="[knowledge] 过滤 .omo/_knowledge/ 下指定文件名 (e.g. bos-metrics)",
    )

    ls_tail = ls_sub.add_parser("tail", help="Tail last N records")
    ls_tail.add_argument("--type", "-t", choices=_log_types, default="kei")
    ls_tail.add_argument("--lines", "-n", type=int, default=10)
    ls_tail.add_argument(
        "--file",
        help="[knowledge] 过滤 .omo/_knowledge/ 下指定文件名 (e.g. bos-metrics)",
    )

    ls_stats = ls_sub.add_parser("stats", help="Log file statistics")
    ls_stats.add_argument("--type", "-t", choices=_log_types, default="kei")
    ls_stats.add_argument(
        "--file",
        help="[knowledge] 过滤 .omo/_knowledge/ 下指定文件名",
    )

    # metric
    sub.add_parser("metric", help="Show aggregated metrics")

    args = parser.parse_args(argv)
    if args.command == "log":
        if args.log_cmd == "search":
            return cmd_log_search(args.type, args.keyword, args.status, args.since, args.limit, args.file)
        elif args.log_cmd == "tail":
            return cmd_log_tail(args.type, args.lines, args.file)
        elif args.log_cmd == "stats":
            return cmd_log_stats(args.type, args.file)
        else:
            ls.print_help()
            return 1
    elif args.command == "metric":
        return cmd_metric_show()
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
