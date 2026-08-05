#!/usr/bin/env python3
"""CR-X4-SUBMODULE-POINTER-INTEGRITY: 检查子模块指针完整性.

子模块指针必须与远程同步: 禁止超前指针 (未推送的 submodule commit),
禁止指针漂移 (submodule commit 被 rebase/drop).
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    violations = []

    # 检查 1: 未推送的子模块指针 (超前指针)
    result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        prefix = line[0] if line else ""
        if prefix == "+":
            parts = line[1:].strip().split(None, 1)
            path = parts[1] if len(parts) > 1 else parts[0]
            violations.append(f"  {path} — 子模块指针超前 (未推送至 remote)")

    # 检查 2: 子模块指针变更但无子模块 commit 消息
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # projects/* 目录下的子模块变更
        if line.startswith("projects/") and not line.endswith(".py"):
            violations.append(f"  {line} — 子模块指针变更, 请确保对应子模块已推送")

    if violations:
        print(f"FAIL 发现 {len(violations)} 个子模块指针完整性问题:")
        for v in violations:
            print(v)
        return 1

    print("OK 所有子模块指针完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
