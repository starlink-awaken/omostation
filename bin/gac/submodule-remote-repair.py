#!/usr/bin/env python3
"""submodule-remote-repair.py — 按 .gitmodules 全量重置子模块 remote URL (批次 24-30 复盘固化).

根因: worktree 共享 gitdir 时, git -C <sub> config 写入主仓共享 config,
多个子模块的 remote.origin.url 互相串联覆盖 (最后写的赢)。

用法: python3 bin/gac/submodule-remote-repair.py [--root <workspace>]
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def read_gitmodules(gm: Path) -> dict[str, str]:
    txt = gm.read_text(encoding="utf-8")
    return dict(re.findall(r"path = (\S+)\n\turl = (\S+)", txt))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    gm = root / ".gitmodules"
    if not gm.is_file():
        raise SystemExit(f".gitmodules not found at {gm}")

    pairs = read_gitmodules(gm)
    fixed: list[str] = []
    still_bad: list[str] = []

    for sub_path, expected in pairs.items():
        sub = root / sub_path
        git_file = sub / ".git"
        if not sub.is_dir() or not git_file.exists():
            continue
        subprocess.run(
            ["git", "-C", str(sub), "config", "remote.origin.url", expected],
            capture_output=True,
            text=True,
        )
        check = subprocess.run(
            ["git", "-C", str(sub), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if check.stdout.strip() == expected:
            fixed.append(sub_path)
        else:
            still_bad.append(f"{sub_path}: {check.stdout.strip()} != {expected}")

    print(f"fixed: {len(fixed)}/{len(pairs)}")
    if still_bad:
        for b in still_bad:
            print(f"STILL BAD: {b}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
