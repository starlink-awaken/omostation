#!/usr/bin/env python3
"""OMO Trail — 第 7 个 AppendOnlyLog consumer (Round 12 P0+P1).

用途: 跟踪 agent / CLI / workflow 的细粒度操作轨迹 (step-by-step).
  - record_step(actor, action, target, status, duration_ms, parent_step_id)
  - read_trail(limit, actor=None, action=None) - 倒序读
  - DEFAULT_PATH = .omo/_knowledge/omo-trail.jsonl

与既有 6 个 consumer 的边界 (Round 12 P1 设计):
  - omo_audit:    治理 action 宏观记录 (e.g. "rebuild model-driven")
  - omo_event:    用户面向 emit 离散事件 (e.g. "custom_event")
  - omo_history:  治理评分周期性快照 (A+/B/C)
  - omo_sync:     omo state sync 状态 (周期性)
  - omo_alert:    KEI threshold 阈值告警
  - omo_bos_metrics: BOS invoke 监控
  - omo_trail:    **细粒度步骤轨迹** (step-by-step, 可嵌套, 含耗时)

差异点:
  - 每条带 duration_ms (执行耗时) - 其他 consumer 不关心
  - 支持 parent_step_id (嵌套调用图) - 适合 agent/CLI 嵌套场景
  - actor 字段强制 (谁做的) - 区分 user/agent/cli
  - 走 Pydantic schema 校验 (Round 9 P0 写时锁)

设计动机 (Round 12 P1):
  - 6 个 consumer 模式成熟 (Round 1-7 全过审计 100.0)
  - 第 7 个 = 拓展到"团队层"治理可见性: 任何模块都可以"打点"操作轨迹
  - 与 omo_audit 互补: audit 看"做了什么决策", trail 看"走完几步完成"

CLI:
    omo trail record --actor user --action edit --target omo_trail.py --duration-ms 120
    omo trail record --actor agent:foo --action exec --target 'git status' --status ok --duration-ms 50
    omo trail show --limit 20
    omo trail show --actor user --limit 50
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from omo.omo_io import AppendOnlyLog
from omo.omo_io_schemas import OmoTrailRecord


_WORKSPACE = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
DEFAULT_TRAIL_PATH = _WORKSPACE / ".omo" / "_knowledge" / "omo-trail.jsonl"


def record_step(
    *,
    actor: str,
    action: str,
    target: str,
    status: str = "ok",
    duration_ms: int = 0,
    parent_step_id: str | None = None,
    log_path: Path | str = DEFAULT_TRAIL_PATH,
) -> dict[str, object]:
    """追加一条 trail step (AppendOnlyLog 写, Pydantic schema 校验).

    Args:
        actor: 谁做的 (e.g. "user", "agent:cursor", "cli:omo").
        action: 做了什么 (e.g. "edit", "read", "exec", "compile", "test").
        target: 操作对象 (e.g. "omo_trail.py", "command:git status").
        status: "ok" / "fail" / "skip".
        duration_ms: 耗时 (毫秒, 0 表示瞬间).
        parent_step_id: 父步骤 ID (嵌套场景, None/空 = 顶层).
        log_path: 目标 .jsonl (默认 .omo/_knowledge/omo-trail.jsonl).

    Returns:
        写入的 record dict (Pydantic model_dump 输出).

    Raises:
        pydantic.ValidationError: 字段不通过 OmoTrailRecord 校验.

    Round 12 P0+P1: 第 7 个 AppendOnlyLog consumer 上线样板.
    """
    from omo.omo_audit import _utc_now  # Round 8 P2 锁: Z-suffix 统一

    record_obj = OmoTrailRecord(
        ts=_utc_now(),
        actor=actor,
        action=action,
        target=target,
        status=status,
        duration_ms=duration_ms,
        parent_step_id=parent_step_id or "",
    )
    record = record_obj.model_dump()
    # Round 9 P0: 写时 Pydantic 校验 (schema= 参数)
    AppendOnlyLog(Path(log_path)).append(record, schema=OmoTrailRecord, sort_keys=True)
    return record


def read_trail(
    *,
    log_path: Path | str = DEFAULT_TRAIL_PATH,
    limit: int = 100,
    actor: str | None = None,
    action: str | None = None,
) -> list[dict[str, object]]:
    """读最近 trail steps (倒序, 最新的在前).

    Args:
        log_path: 源 .jsonl (默认 DEFAULT_TRAIL_PATH).
        limit: 最大返回条数 (默认 100).
        actor: 可选 actor 过滤 (e.g. "user", "agent:foo").
        action: 可选 action 过滤 (e.g. "edit", "exec").

    Returns:
        trail steps list (倒序, 最新在前), 长度 ≤ limit.
    """
    log = AppendOnlyLog(Path(log_path))
    records = log.read_all()

    if actor is not None:
        records = [r for r in records if r.get("actor") == actor]
    if action is not None:
        records = [r for r in records if r.get("action") == action]

    # 倒序: 最新在前 (与 omo_history 一致)
    records.reverse()
    if limit > 0:
        return records[:limit]
    return records


def cmd_trail_record(args: argparse.Namespace) -> int:
    """CLI: omo trail record --actor X --action Y --target Z ..."""
    record_step(
        actor=args.actor,
        action=args.action,
        target=args.target,
        status=args.status,
        duration_ms=args.duration_ms,
        parent_step_id=args.parent,
        log_path=args.log,
    )
    print(f"✅ trail step recorded: {args.actor} → {args.action} → {args.target}")
    print(f"   log: {args.log}")
    return 0


def cmd_trail_show(args: argparse.Namespace) -> int:
    """CLI: omo trail show [--limit N] [--actor X] [--action Y]."""
    steps = read_trail(
        log_path=args.log,
        limit=args.limit,
        actor=args.actor,
        action=args.action,
    )
    if not steps:
        print("(空 — 无 trail step 记录)")
        return 0

    # 表头
    print(
        f"{'TS':26s}  {'ACTOR':14s}  {'ACTION':10s}  "
        f"{'TARGET':30s}  {'STATUS':6s}  {'MS':>5s}  PARENT"
    )
    print("-" * 110)
    for s in steps:
        ts = str(s.get("ts", "?"))[:26]
        actor = str(s.get("actor", "?"))
        action = str(s.get("action", "?"))
        target = str(s.get("target", "?") or "?")[:30]
        status = str(s.get("status", "?"))
        # dict.get 返回 object | int, 显式收窄到 int (Pyright strict 模式)
        ms_raw = s.get("duration_ms", 0)
        ms = int(ms_raw) if isinstance(ms_raw, (int, float)) else 0
        parent = str(s.get("parent_step_id", "") or "-")
        print(
            f"{ts:26s}  {actor:14s}  {action:10s}  "
            f"{target:30s}  {status:6s}  {ms:>5d}  {parent}"
        )
    print(f"\nTotal: {len(steps)} steps")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo trail",
        description=(
            "OMO trail (Round 12 P0+P1) — 第 7 个 AppendOnlyLog consumer. "
            "记录细粒度操作轨迹 (step-by-step, 可嵌套, 含耗时)."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    # record 子命令
    rec = sub.add_parser("record", help="追加一条 trail step (走 Pydantic 校验)")
    rec.add_argument("--actor", required=True, help="actor (e.g. user, agent:foo, cli:omo)")
    rec.add_argument("--action", required=True, help="action (e.g. edit, read, exec)")
    rec.add_argument("--target", required=True, help="target (file path / command)")
    rec.add_argument(
        "--status",
        default="ok",
        choices=["ok", "fail", "skip"],
        help="执行状态 (默认 ok)",
    )
    rec.add_argument(
        "--duration-ms",
        type=int,
        default=0,
        help="耗时毫秒 (默认 0)",
    )
    rec.add_argument(
        "--parent",
        default=None,
        help="父 step ID (嵌套场景, 默认 None = 顶层)",
    )
    rec.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_TRAIL_PATH,
        help=f"落点 .jsonl (默认: {DEFAULT_TRAIL_PATH})",
    )

    # show 子命令
    show = sub.add_parser("show", help="显示最近 trail (倒序)")
    show.add_argument("--limit", "-n", type=int, default=20, help="最多显示 N 条 (默认 20)")
    show.add_argument("--actor", default=None, help="按 actor 过滤")
    show.add_argument("--action", default=None, help="按 action 过滤")
    show.add_argument("--log", type=Path, default=DEFAULT_TRAIL_PATH, help=f"源 .jsonl (默认: {DEFAULT_TRAIL_PATH})")

    # seed 子命令 (Round 19 P0: 让 trail 业务真落地, 写 5 条样例 step)
    seed = sub.add_parser("seed", help="写 5 条样例 step (Round 19 P0 — 让 trail.jsonl 出现)")
    seed.add_argument("--log", type=str, default=str(DEFAULT_TRAIL_PATH), help=f"落点 .jsonl (默认: {DEFAULT_TRAIL_PATH})")

    args = parser.parse_args(argv)
    if args.command == "record":
        return cmd_trail_record(args)
    if args.command == "show":
        return cmd_trail_show(args)
    if args.command == "seed":
        from omo.omo_trail_seed import cmd_trail_seed
        # 把 str 转 Path-like 给 record_step (record_step 接 Path | str)
        args.log = Path(args.log)
        return cmd_trail_seed(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
