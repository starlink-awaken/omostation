#!/usr/bin/env python3
"""
统一债务目录守卫 — 检查 .omo/debt/ 下是否有 staged 删除.
"""
import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        ["git", "status", "--short", "--", ".omo/debt/"],
        capture_output=True, text=True, check=True,
    )
    deleted = [line for line in result.stdout.splitlines() if line.startswith("D") or line.startswith(" D")]
    if deleted:
        print("❌ .omo/debt/ 下有关联删除文件:", file=sys.stderr)
        for line in deleted:
            print(f"   {line}", file=sys.stderr)
        print("⛔ 拒绝提交 — 债务文件只能通过 omo debt CLI 管理", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
