#!/usr/bin/env python3
"""state-stale-consume — 消费 state_stale 事件, 触发 omo state sync.

ADR-0128 Phase 2 消费端最小版. 闭环 (健康治理理想态原则4):
  state-stale-emit.py emit state_stale (post-commit/launchd WatchPaths)
    → 本脚本消费
    → omo state sync 刷新运行时投影
    → emit state_sync_complete

治 event-loop-lint 检测到的 state_stale 死回路 (emit 671 条零消费者).
event-loop-lint grep "state_stale" 在 bin/+projects/omo/src/ 判定消费者;
本文件含 state_stale 字符串 (STATE_KIND), 不被 EXCLUDE_RE 排除 (文件名 consume 非 emit/gen/test).

安全性 (ADR-0128 方案 B/D):
  - fcntl.flock 串行化 (防多 agent 并发 sync, ADR-0128 §5.2.1 单写者)
  - omo state sync 本身 write_if_changed (幂等, 内容未变不写盘)

挂载建议:
  - knowledge-foundry-cron 5:59 (event-loop-lint 5:57 之后: 先消费再检测)
  - 或 launchd 每 5 分钟 (ADR-0128 §5.2.2 本地开发调度)
  - agent 手动: python3 bin/gac/state-stale-consume.py --force

用法:
  python3 bin/gac/state-stale-consume.py            # 仅当近 5 分钟有 state_stale 才 sync
  python3 bin/gac/state-stale-consume.py --force    # 无视新鲜度, 强制 sync 一次
  python3 bin/gac/state-stale-consume.py --within 60 --quiet

退出码: 0 = 跳过或 sync 成功; 非 0 = sync 失败.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
EVENTS = WORKSPACE / ".omo" / "_knowledge" / "omo-events.jsonl"
LOCK = WORKSPACE / ".omo" / "_control" / "state-sync.lock"

# 消费的 event kind. event-loop-lint grep 此字符串判定本文件是 state_stale 的消费者.
STATE_KIND = "state_stale"


def parse_ts(ts: str) -> float | None:
    """omo-events.jsonl 的 ts 是 ISO 8601 (如 '2026-07-23T02:15:53Z') → epoch."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def has_fresh_stale(within_s: int) -> tuple[bool, int]:
    """omo-events.jsonl 尾部是否有 within_s 秒内的 state_stale 事件.

    返回 (是否有, state_stale 总计数). 只扫尾部 300 行 (事件 append-only, 新的在后面).
    """
    if not EVENTS.is_file():
        return False, 0
    cutoff = datetime.now(timezone.utc).timestamp() - within_s
    total = 0
    fresh = False
    try:
        lines = EVENTS.read_text(encoding="utf-8").splitlines()[-300:]
    except OSError:
        return False, 0
    for line in lines:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("kind") != STATE_KIND:
            continue
        total += 1
        epoch = parse_ts(str(d.get("ts", "")))
        if epoch is not None and epoch >= cutoff:
            fresh = True
    return fresh, total


def run_sync(timeout: int = 120) -> tuple[int, str]:
    """omo state sync, 带 flock 串行化 (ADR-0128 §5.2.1 单写者)."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0, "另一个 sync 在跑 (flock 占用), 跳过"
        try:
            res = subprocess.run(
                ["uv", "run", "--project", "projects/omo", "omo", "state", "sync"],
                cwd=WORKSPACE, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
            out = (res.stdout + res.stderr).strip()
            return res.returncode, out
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def emit_complete(changed: bool) -> None:
    """emit state_sync_complete (ADR-0128 §5.2.3 事件契约). 失败静默 (不阻塞主流程)."""
    payload = json.dumps(
        {"changed": changed, "consumer": "state-stale-consume.py"},
        ensure_ascii=False, sort_keys=True,
    )
    subprocess.run(
        ["uv", "run", "--project", "projects/omo", "omo", "event", "emit",
         "--type", "state_sync_complete", "--source", "state-stale-consume",
         "--payload", payload],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=30, check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Consume state_stale events → omo state sync")
    parser.add_argument("--within", type=int, default=300,
                        help="仅当近 N 秒内有 state_stale 事件才 sync (默认 300)")
    parser.add_argument("--force", action="store_true",
                        help="无视新鲜度, 强制 sync 一次")
    parser.add_argument("--quiet", action="store_true", help="静默")
    args = parser.parse_args()

    fresh, total = has_fresh_stale(args.within)
    if not args.force and not fresh:
        if not args.quiet:
            print(f"[state-stale-consume] 近 {args.within}s 无 state_stale (总计 {total}), 跳过")
        return 0

    if not args.quiet:
        print(f"[state-stale-consume] 检测到 state_stale (总计 {total}), 触发 omo state sync...")
    rc, out = run_sync()
    if out and not args.quiet:
        print(out[:500])
    emit_complete(changed=(rc == 0))
    if not args.quiet:
        tag = "✅ sync 完成" if rc == 0 else f"❌ sync 失败 (rc={rc})"
        print(f"[state-stale-consume] {tag}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
