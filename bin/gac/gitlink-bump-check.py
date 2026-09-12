#!/usr/bin/env python3
"""gitlink-bump-check.py — 主仓 gitlink bump 前置校验 (批次 28 复盘固化).

检查 (按顺序, 全过才 exit 0):
  1. 每个 bump 的 gitlink SHA 在对应子模块 origin/main 可达 (squash 后的 SHA 必须在远端 main)
  2. bump 是前进 (old 是 new 的祖先), 非回退

用法:
  python3 bin/gac/gitlink-bump-check.py --base origin/main --head HEAD
  (在主仓 worktree / 分支上运行, push 前使用)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def git(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    cmd = ["git"] + (["-C", str(cwd)] if cwd else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()

    rc, diff = git("diff", "--name-only", f"{args.base}...{args.head}")
    if rc != 0:
        print(f"cannot diff {args.base}...{args.head}", file=sys.stderr)
        return 2

    gitlinks = [
        line.strip() for line in diff.splitlines()
        if line and not line.startswith("docs/") and not line.startswith(".omo/")
    ]
    # 只保留 gitlink 文件 (160000): 通过 ls-tree 验证
    real_gitlinks = []
    for path in gitlinks:
        rc2, out = git("ls-tree", args.head, "--", path)
        if rc2 == 0 and out.strip().startswith("160000"):
            real_gitlinks.append(path)

    if not real_gitlinks:
        print("no gitlink bumps found; OK")
        return 0

    failures = 0
    for path in real_gitlinks:
        rc_old, out_old = git("ls-tree", args.base, "--", path)
        old_sha = out_old.split()[2] if rc_old == 0 and out_old.split() else ""
        rc_new, out_new = git("ls-tree", args.head, "--", path)
        new_sha = out_new.split()[2] if rc_new == 0 and out_new.split() else ""
        if not old_sha or not new_sha:
            continue
        # 远端 main 可达性
        rc_contains, _ = git("merge-base", "--is-ancestor", new_sha, "origin/main", cwd=root / path)
        if rc_contains != 0:
            print(f"FAIL {path}: {new_sha[:9]} unreachable from submodule origin/main (squash merge 后必须推到子模块远端 main)", file=sys.stderr)
            failures += 1
            continue
        # 回退检查
        rc_fwd, _ = git("merge-base", "--is-ancestor", old_sha, new_sha, cwd=root / path)
        if rc_fwd != 0 and old_sha != new_sha:
            print(f"FAIL {path}: {old_sha[:9]} -> {new_sha[:9]} is a REWIND (非前进)", file=sys.stderr)
            failures += 1
            continue
        print(f"OK  {path}: {old_sha[:9]} -> {new_sha[:9]} (forward, reachable)")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
