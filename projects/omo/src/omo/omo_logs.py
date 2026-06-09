"""omo logs 统一 CLI (Round 10 P0) — 跨 consumer 查 .omo/_knowledge/*.jsonl.

子命令:
    list   — 列出 .omo/_knowledge/ 下所有 .jsonl 文件, 含大小 / 行数 / mtime
    inspect <name> — 查指定 jsonl 详情 (字段分布, 必填字段缺失, 时间戳格式)
    tail <name> [--lines N] — 读最近 N 条记录 (走 AppendOnlyLog.tail 真正 O(n))
    audit  — 走 SSOT schema 检查, 报漂移 (走 Pydantic 校验)

设计:
    - omo_logs 自身不写, 只读 AppendOnlyLog 实例 (consumer 抽象的 reader)
    - 字段含义 = omo_io_schemas.py (6 个 Pydantic model)
    - 错误信息 → CLI 退出码非 0 (CI lint 友好)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog
from omo.omo_io_schemas import SCHEMA_REGISTRY

_WORKSPACE = Path(
    os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
)
KNOWLEDGE_DIR = _WORKSPACE / ".omo" / "_knowledge"


def _list_log_paths() -> list[Path]:
    """List all .jsonl in .omo/_knowledge/, sorted by mtime (newest first)."""
    if not KNOWLEDGE_DIR.exists():
        return []
    return sorted(
        (p for p in KNOWLEDGE_DIR.glob("*.jsonl") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _resolve_log_path(name: str) -> Path:
    """从 user 给的 name 解析 .jsonl 路径. 支持 'foo' 或 'foo.jsonl'."""
    if (KNOWLEDGE_DIR / name).exists():
        return KNOWLEDGE_DIR / name
    if (KNOWLEDGE_DIR / f"{name}.jsonl").exists():
        return KNOWLEDGE_DIR / f"{name}.jsonl"
    raise FileNotFoundError(f"log not found: {name} (in {KNOWLEDGE_DIR})")


# ── 子命令: list ──────────────────────────────────────────


def cmd_logs_list() -> int:
    """列出所有 .omo/_knowledge/*.jsonl 文件."""
    paths = _list_log_paths()
    if not paths:
        print(f"ℹ️  No logs in {KNOWLEDGE_DIR}")
        return 0
    print(f"{'NAME':30s} {'SIZE':>10s} {'RECORDS':>10s} {'MTIME':20s}")
    print("-" * 75)
    for p in paths:
        log = AppendOnlyLog(p)
        try:
            records = log.read_all()
            count = len(records)
        except Exception:
            count = -1
        size = p.stat().st_size
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{p.stem:30s} {size:>10,} {count:>10,} {mtime:20s}")
    return 0


# ── 子命令: inspect ──────────────────────────────────────────


def cmd_logs_inspect(name: str) -> int:
    """查指定 jsonl 字段分布 + 必填字段缺失 + 时间戳格式."""
    try:
        path = _resolve_log_path(name)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    log = AppendOnlyLog(path)
    records = log.read_all()
    if not records:
        print(f"ℹ️  {path.name}: empty")
        return 0

    # 字段分布
    field_counter: Counter = Counter()
    for r in records:
        if isinstance(r, dict):
            for k in r.keys():
                field_counter[k] += 1

    # 必填字段缺失
    schema_name = _infer_schema_name(path.stem)
    missing_required: list[tuple[int, set]] = []
    ts_z_suffix_count = 0
    if schema_name and schema_name in SCHEMA_REGISTRY:
        schema_cls = SCHEMA_REGISTRY[schema_name]
        required = set(schema_cls.model_fields.keys())
        for i, r in enumerate(records):
            if not isinstance(r, dict):
                continue
            missing = required - set(r.keys())
            if missing:
                missing_required.append((i, missing))
            # 时间戳 Z 结尾校验
            ts = r.get("ts") or r.get("recorded_at") or r.get("timestamp")
            if ts and isinstance(ts, str) and ts.endswith("Z"):
                ts_z_suffix_count += 1

    print(f"📄 {path.name}: {len(records):,} records, {path.stat().st_size:,} bytes")
    print(f"\n字段分布 (top 10):")
    for field, count in field_counter.most_common(10):
        print(f"  {field:30s} {count:>10,}")
    if schema_name:
        print(f"\nSchema 推断: {schema_name} ({len(SCHEMA_REGISTRY[schema_name].model_fields)} 必填字段)")
    if missing_required:
        print(f"\n⚠️  {len(missing_required)} 条记录缺必填字段:")
        for i, missing in missing_required[:5]:
            sample = records[i] if i < len(records) else {}
            print(f"  line {i}: missing {sorted(missing)} (keys: {list(sample.keys()) if isinstance(sample, dict) else '?'})")
        if len(missing_required) > 5:
            print(f"  ... +{len(missing_required) - 5} more")
    else:
        print(f"\n✅ 所有 records 符合必填字段 (Round 8 P2 SSOT)")
    if ts_z_suffix_count < len(records):
        bad = len(records) - ts_z_suffix_count
        print(f"⚠️  {bad} 条 records 时间戳不是 'Z' 结尾 (Round 8 P2 锁)")
    return 0


def _infer_schema_name(file_stem: str) -> str | None:
    """从文件名推断 schema. e.g. 'bos-metrics' → 'omo_bos_metrics'.

    Round 10 P0 锁: 文件名 ≠ SSOT key 时, 走显式映射表
    (SSOT_KEYS 是 AppendOnlyLog 抽象的 6 个 consumer, 实际文件名是另一回事).
    """
    # 显式映射 (文件名 → SSOT key)
    file_to_schema: dict[str, str] = {
        "bos-metrics": "omo_bos_metrics",
        "omo-events": "omo_event",
        "omo-alerts": "omo_alert",
        "omo-sync": "omo_sync",
        "governance-history": "omo_history",
        "pipeline-events": "omo_sync",  # 近似 (PipelineTracker 也用 ts+kind)
    }
    if file_stem in file_to_schema:
        return file_to_schema[file_stem]
    if file_stem in SCHEMA_REGISTRY:
        return file_stem
    normalized = file_stem.replace("-", "_")
    if normalized in SCHEMA_REGISTRY:
        return normalized
    return None


# ── 子命令: tail ──────────────────────────────────────────


def cmd_logs_tail(name: str, lines: int) -> int:
    """读指定 jsonl 最近 N 条 (走 AppendOnlyLog.tail 真正 O(n))."""
    try:
        path = _resolve_log_path(name)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    log = AppendOnlyLog(path)
    records = log.tail(lines)
    if not records:
        print(f"ℹ️  {path.name}: empty")
        return 0
    print(f"Last {len(records)} records from {path.name}:")
    print()
    for r in records:
        if isinstance(r, dict):
            ts = r.get("ts") or r.get("recorded_at") or r.get("timestamp", "?")
            action = r.get("action") or r.get("status") or r.get("kind") or r.get("uri") or r.get("severity") or "?"
            detail = r.get("details") or r.get("error") or r.get("payload") or r.get("message") or ""
            if isinstance(detail, str):
                detail = detail[:80]
            print(f"  [{ts}] {action}: {detail}")
        else:
            print(f"  {r}")
    return 0


# ── 子命令: audit ──────────────────────────────────────────


def cmd_logs_audit(consumer: str | None = None) -> int:
    """走 SSOT schema 检查所有 .jsonl, 报漂移.

    Args:
        consumer: 限定 audit 单个 consumer (e.g. 'omo-bos-metrics'). None = audit 所有.
    """
    paths = _list_log_paths()
    if consumer:
        try:
            paths = [p for p in paths if p.stem == consumer or p.stem.replace("-", "_") == consumer]
        except Exception:
            pass
        if not paths:
            print(f"❌ consumer not found: {consumer}", file=sys.stderr)
            return 1

    total_failures = 0
    total_records = 0
    for p in paths:
        log = AppendOnlyLog(p)
        records = log.read_all()
        total_records += len(records)
        schema_name = _infer_schema_name(p.stem)
        if not schema_name:
            print(f"⚠️  {p.stem}: no schema mapped, skipping SSOT check")
            continue
        schema_cls = SCHEMA_REGISTRY[schema_name]
        required = set(schema_cls.model_fields.keys())
        failures = 0
        parse_errors = 0
        for i, r in enumerate(records):
            if not isinstance(r, dict):
                parse_errors += 1
                continue
            missing = required - set(r.keys())
            if missing:
                failures += 1
        if failures or parse_errors:
            print(f"❌ {p.stem} ({schema_name}): {failures} schema drift, {parse_errors} parse errors (out of {len(records)} records)")
            total_failures += failures
        else:
            print(f"✅ {p.stem} ({schema_name}): {len(records):,} records 符合 SSOT")

    print(f"\n总计: {total_records:,} records, {total_failures} 漂移")
    return 0 if total_failures == 0 else 1


# ── 主入口 ──────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo logs",
        description="统一管理 .omo/_knowledge/*.jsonl (Round 10 P0 — AppendOnlyLog 用户面 CLI)",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help=f"列出 {KNOWLEDGE_DIR} 下所有 .jsonl")

    # inspect
    ins = sub.add_parser("inspect", help="查指定 jsonl 字段分布 + 必填字段缺失")
    ins.add_argument("name", help="jsonl 文件名 (e.g. 'bos-metrics' 或 'bos-metrics.jsonl')")

    # tail
    tl = sub.add_parser("tail", help="读指定 jsonl 最近 N 条 (AppendOnlyLog.tail 真正 O(n))")
    tl.add_argument("name", help="jsonl 文件名")
    tl.add_argument("--lines", "-n", type=int, default=10)

    # audit
    au = sub.add_parser("audit", help="走 SSOT schema 检查所有 .jsonl, 报漂移")
    au.add_argument("--consumer", help="限定 audit 单个 consumer (e.g. 'omo-bos-metrics')")

    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_logs_list()
    if args.command == "inspect":
        return cmd_logs_inspect(args.name)
    if args.command == "tail":
        return cmd_logs_tail(args.name, args.lines)
    if args.command == "audit":
        return cmd_logs_audit(args.consumer)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
