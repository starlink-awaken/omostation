#!/usr/bin/env python3
"""
拒绝直接 push 到 main 分支 (work/* 和 pr/* 除外).
"""
import subprocess
import sys


def main() -> int:
    # 读取 stdin (pre-push 传递的 push refs)
    import os
    push_refs = sys.stdin.read() if not sys.stdin.isatty() else ""

    current_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    # 检查是否 push main
    for line in push_refs.splitlines():
        if "refs/heads/main" in line:
            if not (current_branch.startswith("work/") or current_branch.startswith("pr/")):
                print(f"[blocking] ❌ 拒绝直接 push 至 main (当前分支: {current_branch})", file=sys.stderr)
                print("   请使用 work/* 分支 + PR 合流", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
