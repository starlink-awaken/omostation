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
    print("\n字段分布 (top 10):")
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
        print("\n✅ 所有 records 符合必填字段 (Round 8 P2 SSOT)")
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


def cmd_logs_audit(
    consumer: str | None = None,
    baseline_init: str | None = None,
    baseline_check: str | None = None,
) -> int:
    """走 SSOT schema 检查所有 .jsonl, 报漂移.

    Round 13 P0 新增 baseline 机制 (实现 Round 12 P0 commit flag 的 TODO):
      - 老 .jsonl 漂移是历史问题, 不应阻塞新代码提交
      - 启动时跑一次 --baseline-init 把当前 drift 写入 baseline 文件
      - pre-commit 跑 --baseline-check, drift > baseline 才 fail
      - 新代码引入的'增量漂移'才 fail, 老数据自动忽略

    Args:
        consumer: 限定 audit 单个 consumer (e.g. 'omo-bos-metrics'). None = audit 所有.
        baseline_init: 路径, 写入当前 drift 为 baseline (生成/刷新).
        baseline_check: 路径, 对比 baseline, 增量 > 0 才 fail (pre-commit 用).

    Returns:
        0 = pass (无漂移, 或 baseline-check 0 增量)
        1 = fail (有漂移, 或 baseline-check 有回归)
    """
    paths = _list_log_paths()
    if consumer:
        paths = [p for p in paths if p.stem == consumer or p.stem.replace("-", "_") == consumer]
        if not paths:
            print(f"❌ consumer not found: {consumer}", file=sys.stderr)
            return 1

    total_records = 0
    # 按 schema_name 累计 drift (而非按文件名, baseline 用 schema 维度更稳定)
    drift_by_consumer: dict[str, int] = {}
    file_results: list[tuple[Path, str, int, int]] = []  # (path, schema_name, drift, parse_errors)

    for p in paths:
        log = AppendOnlyLog(p)
        records = log.read_all()
        total_records += len(records)
        schema_name = _infer_schema_name(p.stem)
        if not schema_name:
            print(f"⚠️  {p.stem}: no schema mapped, skipping SSOT check")
            continue
        # Round 11 /simplify 修: 单 pass 累计 drift + parse_errors (vs 旧版 2 次遍历)
        required = set(SCHEMA_REGISTRY[schema_name].model_fields.keys())
        failures = parse_errors = 0
        for r in records:
            if not isinstance(r, dict):
                parse_errors += 1
                continue
            if set(r.keys()) != required and not required.issubset(r.keys()):
                # 仅当缺字段时报 (多余字段允许, forward compat)
                failures += 1
        file_results.append((p, schema_name, failures, parse_errors))
        drift_by_consumer[schema_name] = drift_by_consumer.get(schema_name, 0) + failures

    # ── 模式 1: --baseline-init (生成/刷新 baseline) ──
    if baseline_init is not None:
        baseline_path = Path(baseline_init)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_comment": (
                "AppendOnlyLog audit baseline (Round 13 P0). "
                "漂移 = 已知/历史缺失, pre-commit 应忽略. "
                "新代码引入'增量'漂移才 fail. "
                "刷新: omo logs audit --baseline-init <this_path>."
            ),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "drift_by_consumer": dict(sorted(drift_by_consumer.items())),
            "total_drift": sum(drift_by_consumer.values()),
            "total_records": total_records,
        }
        baseline_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"✅ baseline 写入: {baseline_path}")
        print(f"   total_records: {total_records:,}")
        print(f"   total_drift:   {sum(drift_by_consumer.values())}")
        print(f"   consumers ({len(drift_by_consumer)}):")
        for k, v in sorted(drift_by_consumer.items()):
            print(f"     {k}: {v}")
        return 0

    # ── 模式 2: --baseline-check (对比 baseline, 增量才 fail) ──
    if baseline_check is not None:
        baseline_path = Path(baseline_check)
        if not baseline_path.exists():
            print(
                f"❌ baseline 不存在: {baseline_path}",
                file=sys.stderr,
            )
            print(
                f"   初始化: omo logs audit --baseline-init {baseline_path}",
                file=sys.stderr,
            )
            return 1
        try:
            baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
            # 兼容两种格式: 新格式 {drift_by_consumer: {...}} + 旧格式 (平铺 dict)
            if "drift_by_consumer" in baseline_payload:
                baseline_drift: dict[str, int] = baseline_payload["drift_by_consumer"]
            else:
                baseline_drift = baseline_payload  # type: ignore[assignment]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"❌ baseline 解析失败: {exc}", file=sys.stderr)
            return 1

        any_regression = False
        delta_total = 0
        # 当前有 audit 数据的 consumer
        for k, v in sorted(drift_by_consumer.items()):
            base = baseline_drift.get(k, 0)
            delta = v - base
            if delta > 0:
                print(f"❌ {k}: drift {v} (baseline {base}, +{delta} 回归)")
                any_regression = True
                delta_total += delta
            elif delta < 0:
                print(f"✅ {k}: drift {v} (baseline {base}, {-delta} 改善)")
            else:
                print(f"✅ {k}: drift {v} (baseline {base}, 不变)")
        # baseline 记录但当前无数据 (consumer 临时为空)
        for k in sorted(baseline_drift):
            if k not in drift_by_consumer:
                print(f"⚠️  {k}: baseline 存在但当前无 audit 数据 (skip)")
        if any_regression:
            print(f"\n❌ baseline check fail: 增量 drift {delta_total} (有回归, 新代码引入漂移)")
            return 1
        print("\n✅ baseline check pass: 0 增量 drift (新代码未引入新漂移)")
        return 0

    # ── 模式 3: 默认 (无 baseline) ──
    total_failures = 0
    for p, schema_name, failures, parse_errors in file_results:
        if failures or parse_errors:
            print(
                f"❌ {p.stem} ({schema_name}): {failures} schema drift, "
                f"{parse_errors} parse errors (out of {len(AppendOnlyLog(p).read_all())} records)"
            )
            total_failures += failures
        else:
            print(f"✅ {p.stem} ({schema_name}): {len(AppendOnlyLog(p).read_all()):,} records 符合 SSOT")

    print(f"\n总计: {total_records:,} records, {total_failures} 漂移")
    if total_failures:
        print("   提示: 用 --baseline-init 生成 baseline, 后续 --baseline-check 仅查增量")
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
    au.add_argument(
        "--baseline-init",
        metavar="PATH",
        help="写入当前 drift 为 baseline (生成/刷新 baseline 文件)",
    )
    au.add_argument(
        "--baseline-check",
        metavar="PATH",
        help="对比 baseline, 增量 drift > 0 才 fail (pre-commit 用)",
    )

    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_logs_list()
    if args.command == "inspect":
        return cmd_logs_inspect(args.name)
    if args.command == "tail":
        return cmd_logs_tail(args.name, args.lines)
    if args.command == "audit":
        return cmd_logs_audit(
            consumer=args.consumer,
            baseline_init=args.baseline_init,
            baseline_check=args.baseline_check,
        )
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
