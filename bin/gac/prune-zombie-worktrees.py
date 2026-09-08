#!/usr/bin/env python3
"""prune-zombie-worktrees.py — 僵尸 worktree 清理 (T10-127, 吸收 gac-worktree-cleanup.sh)

僵尸判定 (三规则并集, 任一命中即僵尸):
  1. worktree 目录无 .git 文件 (checkout 损坏)
  2. 最后活动 (mtime) 超过 TTL (默认 7 天)
  3. 分支已完全合并进 origin/main 且无未推送 commit

安全: 默认 dry-run; --enforce 才真删; 有未提交改动的 worktree 永远跳过;
     删除时联动清理 D2 branch claim (防 occupancy 假占用)。

用法:
  python3 bin/gac/prune-zombie-worktrees.py            # dry-run 报告
  python3 bin/gac/prune-zombie-worktrees.py --enforce  # 实删
  python3 bin/gac/prune-zombie-worktrees.py --enforce --ttl-days 3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd or WS_ROOT)
    return r.stdout.strip() if r.returncode == 0 else ""


def _claim_release(session: str) -> None:
    cli = WS_ROOT / "bin/gac/swarm-discipline-cli.py"
    if cli.exists():
        subprocess.run(
            [sys.executable, str(cli), "branch-release", "--session", session],
            capture_output=True, timeout=30,
        )


def _cleanup_guard(branch: str) -> str | None:
    """T10-140: 删除前置引用保护 (共享 lib/cleanup-guard; 加载失败宽容放行)."""
    try:
        sys.path.insert(0, str(WS_ROOT / "lib"))
        import cleanup_guard
        return cleanup_guard.protect_reason(branch)
    except Exception as exc:  # noqa: BLE001 — guard 故障不阻断清理主流程
        print(f"    ⚠️  guard 跳过 ({exc})")
        return None


def scan_zombies(ws_parent: Path, ttl_days: int) -> list[dict]:
    now = time.time()
    zombies: list[dict] = []
    for wt in sorted(ws_parent.glob("ws-*")):
        gitfile = wt / ".git"
        # 规则 1: checkout 损坏
        if not gitfile.exists():
            zombies.append({"path": str(wt), "reasons": ["no-gitfile"], "session": wt.name.removeprefix("ws-")})
            continue
        branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt)
        session = wt.name.removeprefix("ws-")
        # 有未提交改动 → 永远跳过
        if _git("status", "--porcelain", cwd=wt):
            zombies.append({"path": str(wt), "reasons": ["dirty-skip"], "skip": True})
            continue
        reasons: list[str] = []
        # 规则 2: TTL 无活动
        files = [f for f in wt.rglob("*") if f.is_file()]
        mtime = max((f.stat().st_mtime for f in files), default=0)
        age_days = (now - mtime) / 86400
        if age_days > ttl_days:
            reasons.append(f"idle-{age_days:.1f}d")
        # 规则 3: 已合并且无未推 commit
        if branch and branch != "HEAD":
            unpushed = _git("log", "--oneline", "--not", "origin/main", branch, cwd=wt)
            merged = [b.strip().lstrip("* ") for b in _git("branch", "--merged", "origin/main", cwd=wt).splitlines()]
            if not unpushed and branch in merged:
                reasons.append("merged-clean")
        if reasons:
            zombies.append({"path": str(wt), "reasons": reasons, "session": session, "branch": branch})
    return zombies


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--enforce", action="store_true", help="真删 (默认 dry-run)")
    ap.add_argument("--ttl-days", type=int, default=7)
    args = ap.parse_args()

    ws_parent = WS_ROOT.parent
    zombies = scan_zombies(ws_parent, args.ttl_days)
    mode = "ENFORCE" if args.enforce else "DRY-RUN"
    print(f"=== Zombie Worktree 扫描 ({mode}, ttl={args.ttl_days}d) ===")
    removed = 0
    for z in zombies:
        if z.get("skip"):
            print(f"  ⏭  跳过 (有未提交改动): {z['path']} — 请人工处理")
            continue
        print(f"  僵尸: {z['path']} [{', '.join(z['reasons'])}]")
        if args.enforce and z.get("session"):
            # T10-140 引用保护: 分支有未推 commit / open PR / 活跃认领 → 只删 worktree 留分支
            guard_skip = False
            if z.get("branch") and z["branch"] != "HEAD":
                guard = _cleanup_guard(z["branch"])
                if guard is not None:
                    print(f"    ⛔ 分支保留 (引用保护 {guard}): {z['branch']}")
                    guard_skip = True
            subprocess.run(["git", "worktree", "remove", "--force", z["path"]],
                           capture_output=True)
            if z.get("branch") and z["branch"] != "HEAD" and not guard_skip:
                subprocess.run(["git", "branch", "-D", z["branch"]], capture_output=True)
            _claim_release(z["session"])
            removed += 1
    print(f"=== 结果: 发现 {len(zombies)} (跳过 {sum(1 for z in zombies if z.get('skip'))}), 实删 {removed} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
