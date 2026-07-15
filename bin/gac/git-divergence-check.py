#!/usr/bin/env python3
"""git-divergence-check — root main 与 origin/main 分叉检测 (ADR-0202 D3).

foundry deck 用法: 每 6h 检测, ahead+behind >= 阈值 (默认 12) 时 exit 1 → deck fail
→ BRIEF/决策收件箱可见。分叉在 1-2 commit 时调和零成本, 20+ 是小时级工程。

只 fetch root (2s 级); 子模块不逐一 fetch (避免拖慢 cron), 用 --submodules 显式开。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def git(*args: str, cwd: Path = WORKSPACE, timeout: int = 60) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    ).stdout.strip()


def ahead_behind(cwd: Path, local: str = "main", remote: str = "origin/main") -> tuple[int, int]:
    out = git("rev-list", "--left-right", "--count", f"{local}...{remote}", cwd=cwd)
    parts = out.split()
    if len(parts) != 2:
        return (-1, -1)
    return int(parts[0]), int(parts[1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=12, help="ahead+behind 告警阈值")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--submodules", action="store_true", help="逐子模块检测 (慢, 各需 fetch)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.no_fetch:
        try:
            git("fetch", "-q", "origin", timeout=90)
        except subprocess.TimeoutExpired:
            print("⚠ fetch 超时, 用现有 origin ref")

    ahead, behind = ahead_behind(WORKSPACE)
    total = max(ahead, 0) + max(behind, 0)
    report = {
        "root": {"ahead": ahead, "behind": behind},
        "threshold": args.threshold,
        "ok": 0 <= total < args.threshold and ahead >= 0,
        "submodules": {},
    }

    if args.submodules:
        for line in git("submodule", "status").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                sub = WORKSPACE / parts[1]
                try:
                    git("fetch", "-q", "origin", cwd=sub, timeout=60)
                    a, b = ahead_behind(sub, "HEAD")
                    report["submodules"][parts[1]] = {"ahead": a, "behind": b}
                except Exception as e:  # noqa: BLE001
                    report["submodules"][parts[1]] = {"error": str(e)[:80]}

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        state = "✅" if report["ok"] else "❌"
        print(f"{state} root main vs origin/main: ahead {ahead} / behind {behind} "
              f"(阈值 {args.threshold})")
        if not report["ok"]:
            print("  → 分叉正在复利, 尽快调和: 子模块双线合并 → 根仓 merge → worktree+PR")
        for name, s in report["submodules"].items():
            print(f"  {name}: {s}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
