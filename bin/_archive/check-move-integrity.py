#!/usr/bin/env python3
"""check-move-integrity — pre-commit 守卫: 迁移必须保内容 (ADR-0202 D2).

拦截两类 a615ace16 模式 (bin/ rationalization 123 文件 0 字节事件):
  1. 暂存区新增 (A) 的 *.py 为 0 字节 — 骨架占位必须显式内容 (如 '# placeholder')
  2. "删 >0 字节 + 同名新增 0 字节" 迁移对 — 移动丢内容

纯本地 git diff --cached, <1s。exit 1 = 拦截。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def staged_name_status() -> list[tuple[str, str]]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "-M"],
        capture_output=True, text=True, check=False,
    ).stdout
    entries: list[tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            entries.append((parts[0], parts[-1]))  # (status, new_path)
    return entries


def staged_size(path: str) -> int:
    """暂存区 blob 大小 (非工作树)。"""
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", path],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    if len(out) < 2:
        return -1
    blob = out[1]
    cat = subprocess.run(
        ["git", "cat-file", "-s", blob], capture_output=True, text=True, check=False
    )
    try:
        return int(cat.stdout.strip())
    except ValueError:
        return -1


def main() -> int:
    entries = staged_name_status()
    added = [p for s, p in entries if s == "A" and p.endswith(".py")]
    deleted = {Path(p).name for s, p in entries if s == "D"}

    violations: list[str] = []
    for p in added:
        size = staged_size(p)
        if size == 0:
            kind = "迁移丢内容 (同名删除对存在)" if Path(p).name in deleted else "新增 0 字节骨架"
            violations.append(f"  {p} — {kind}")

    if violations:
        print("❌ move-integrity (ADR-0202 D2): 暂存区含 0 字节 *.py:")
        print("\n".join(violations))
        print("  骨架占位请写入显式内容 (如 '# placeholder: <原因>'); 迁移请带内容一起 git mv。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
