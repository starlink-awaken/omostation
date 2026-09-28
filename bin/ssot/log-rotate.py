#!/usr/bin/env python3
"""日志轮转 — 可观测性 P1.2 (design: docs/observability-unified-architecture.md).

轮转分散的 launchd 守护日志 (此前无 logrotate/RotatingFileHandler, 无限增长).
规则:
  - 超过 --max-bytes (默认 5MB) 的文件 → 轮转 (保留 --keep 份 .1/.2/...)
  - 保留份数 (--keep, 默认 3)
  - 轮转 = 历史份 rename 链 (log.1 → log.2 → ...) + 当前份 copytruncate (复制到 log.1 后原地截断)
    当前份不能 rename: launchd 守护的 StandardOutPath 在进程启动时打开一次, rename 后进程继续写
    旧 inode, 下一轮删掉 .N 即写进已删除文件 → 日志不可见 (agent-tick-daemon 2026-09-28 实测)。
    launchd 以 O_APPEND 打开, 截断后进程从 0 续写, 与 logrotate copytruncate 语义一致。

用法:
  python3 bin/ssot/log-rotate.py --dry-run     # 只看不动
  python3 bin/ssot/log-rotate.py               # 执行轮转
  python3 bin/ssot/log-rotate.py --max-bytes 10485760 --keep 5
"""

from __future__ import annotations

import argparse
import os
import shutil
import time
from pathlib import Path

HOME = Path.home()
WORKSPACE = Path(__file__).resolve().parents[2]

# 已知日志路径 (launchd StandardOut/ErrorPath + 守护输出)
LOG_PATHS = [
    HOME / ".agora" / "logs",
    WORKSPACE / ".omo" / "_delivery",
    # 2026-09-28: .omo/_delivery 直属无 .log, 日志全在子目录, 非递归 glob 漏掉
    # resident-orchestrator/daemon.log (18.75MB, 超 5MB 阈值 3.7 倍, 2026-09-15 起
    # 持续增长而从不轮转 —— --dry-run 曾报 "0 over 5242880 bytes")。
    # 此处**只补这一个目录**, 不改成 rglob: /tmp 同在 LOG_PATHS 内, rglob 会扫到
    # 并发 agent 的 worktree/scratchpad (101 个文件), 且 .omo/_delivery 下的
    # 追加式账本 (*.jsonl) 会被 --daily 按 mtime 轮转清零。详见下方 SKIP_NAMES。
    WORKSPACE / ".omo" / "_delivery" / "resident-orchestrator",
    WORKSPACE / ".omo" / "_log",
    WORKSPACE / "runtime" / "logs",
    HOME / ".local" / "state" / "omostation",
    Path("/tmp"),
]

LOG_PATTERNS = ("*.log", "*.out.log", "*.err.log", "*.jsonl", "*.err")
# T9-01 ②: 裸 .err (launchd StandardErrorPath) 此前不匹配任何 pattern —
# 旧错误无限累积并被误读为当前问题 (2026-08-08 Xcode 路径旧错案)
SKIP_NAMES = {
    "agora-events.json",
    "agora-proxy-services.json",
    "agora-audit.db",
    # 2026-09-28: 追加式账本不是日志 —— 轮转 = copytruncate = 清零 = 证据链丢失。
    # receipts.jsonl 随新增的 resident-orchestrator 目录进入扫描范围, 必须排除。
    # 同族账本 (未纳入本 LOG_PATHS, 故暂无暴露, 一并登记以防将来被加进来):
    #   .omo/_delivery/agent-workflows/events.jsonl   workflow 事件账本
    #   .omo/_delivery/ingress/value-evidence.jsonl  BET 价值证据
    #   .omo/_delivery/observability/events.jsonl
    # 根本缺口: 仓内无「日志 vs 追加式状态」SSOT, 靠人工枚举。已记录待立项。
    "receipts.jsonl",
}


def _candidate_files() -> list[Path]:
    out: list[Path] = []
    for base in LOG_PATHS:
        if not base.is_dir():
            continue
        for pattern in LOG_PATTERNS:
            for p in base.glob(pattern):
                if p.name in SKIP_NAMES:
                    continue
                if p.name.startswith("."):
                    continue
                out.append(p)
    # 去重 (可能有重叠 glob)
    return sorted(set(out))


def _rotate_one(path: Path, keep: int, dry_run: bool) -> bool:
    size = path.stat().st_size
    if size == 0:
        return False
    # rename 链: log.keep-1 → 删; log.N → log.N+1; log → log.1
    for i in range(keep - 1, 0, -1):
        src = path.with_name(f"{path.name}.{i}")
        dst = path.with_name(f"{path.name}.{i + 1}")
        if src.exists():
            if dry_run:
                print(f"  [dry-run] {src.name} -> {dst.name}")
            else:
                dst.unlink(missing_ok=True)
                src.rename(dst)
    if dry_run:
        print(f"  [dry-run] {path.name} ({size} bytes) -> {path.name}.1")
    else:
        dst = path.with_name(f"{path.name}.1")
        dst.unlink(missing_ok=True)
        shutil.copyfile(path, dst)
        os.truncate(path, 0)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-bytes", type=int, default=5 * 1024 * 1024, help="轮转阈值 (默认 5MB)")
    parser.add_argument("--keep", type=int, default=3, help="保留份数 (默认 3)")
    parser.add_argument(
        "--daily",
        action="store_true",
        help="按天轮转模式: 跨天 (mtime 非今日) 的日志即使未超阈值也轮转 (T9-01 ②)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidates = _candidate_files()
    over = [p for p in candidates if p.stat().st_size > args.max_bytes]
    if args.daily:
        today = time.strftime("%Y-%m-%d", time.localtime())
        stale_daily = [
            p
            for p in candidates
            if p not in over
            and p.stat().st_size > 0
            and time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime)) != today
        ]
        over = over + stale_daily
    print(f"log-rotate: {len(candidates)} candidate(s), {len(over)} over {args.max_bytes} bytes")
    rotated = 0
    for p in over:
        print(f"  rotate: {p} ({p.stat().st_size} bytes)")
        if _rotate_one(p, args.keep, args.dry_run):
            rotated += 1
    print(f"log-rotate: {'[dry-run] ' if args.dry_run else ''}{rotated} rotated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
