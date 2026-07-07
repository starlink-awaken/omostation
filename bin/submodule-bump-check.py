#!/usr/bin/env python3
"""submodule-bump-check.py — P76 Phase 4 主仓-子仓对称修复

检测 root .gitmodules 声明的 submodule 与 projects/*/.git/HEAD 实际指针的偏离。

当某个 submodule 内部 commit 推进, 但主仓根 commit 没跟, 此工具报 stale.
CI gate 会 fail.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


def list_submodules() -> list[str]:
    """从 .gitmodules 列出所有 submodule path."""
    gm = WORKSPACE / ".gitmodules"
    if not gm.exists():
        return []
    paths: list[str] = []
    current: str | None = None
    for line in gm.read_text().splitlines():
        line = line.strip()
        if line.startswith("[submodule"):
            current = None
        elif line.startswith("path ="):
            current = line.split("=", 1)[1].strip()
            paths.append(current)
    return paths


def submodule_pin(path: str) -> str | None:
    """主仓记录的 submodule HEAD commit SHA.

    用 `git submodule status <path>` 取 pin SHA, 比 ls-files 更稳.
    """
    try:
        result = subprocess.run(
            ["git", "submodule", "status", path],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    if not result.stdout.strip():
        return None
    # output format: "[+- ]<sha> <path> (<describe>)"
    line = result.stdout.strip().splitlines()[0]
    sha = line.split()[0].lstrip("+- ")
    return sha if sha and sha != "-" else None


def submodule_actual(path: str) -> str | None:
    """submodule 自身 HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=WORKSPACE / path,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    out = result.stdout.strip()
    return out if out else None


def main() -> int:
    paths = list_submodules()
    print(f"=== submodule-bump-check ({len(paths)} submodules) ===")
    stale: list[tuple[str, str | None, str | None]] = []
    missing_subdir: list[str] = []
    for path in paths:
        full = WORKSPACE / path
        if not (full / ".git").exists():
            missing_subdir.append(path)
            print(f"  ⚠️  {path}: .git missing (submodule not initialized)")
            continue
        pin = submodule_pin(path)
        actual = submodule_actual(path)
        if pin != actual:
            stale.append((path, pin, actual))
            print(f"  ❌ {path}: pin={pin[:8] if pin else '?'} actual={actual[:8] if actual else '?'}")
        else:
            print(f"  ✅ {path}: {pin[:8] if pin else '?'}")
    print()
    print(f"stale: {len(stale)}, missing_subdir: {len(missing_subdir)}")
    if stale:
        print("\nstale submodules need bump in main repo:")
        for path, pin, actual in stale:
            print(f"  {path}: pin={pin} actual={actual}")
            print(f"    fix: git add {path} && git commit -m 'chore(submodule): bump {path}'")
    return 0 if not stale else 1


if __name__ == "__main__":
    sys.exit(main())
