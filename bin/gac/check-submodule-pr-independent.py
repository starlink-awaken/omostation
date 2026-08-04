#!/usr/bin/env python3
"""CR-P76-8-1-SUBMODULE-PR-INDEPENDENT: 检查子模块 PR 独立性。

确保跨仓 PR 独立提交，不在主仓 commit submodule 内容。
检查 git diff 中是否包含 submodule 指针变更但无对应子模块 commit。
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    # 检查是否有未提交的子模块变更
    result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    violations = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # 格式:  [+/-]hash path (branch)
        prefix = line[0] if line else ""
        if prefix == "+":
            # 子模块指针超前（有未推送的 commit）
            parts = line[1:].strip().split(None, 1)
            if parts:
                path = parts[1] if len(parts) > 1 else parts[0]
                violations.append(f"  {path} — 子模块指针超前，未推送")

    if violations:
        print(f"FAIL {len(violations)} 个子模块指针未同步:")
        for v in violations:
            print(v)
        return 1

    print("OK 所有子模块指针已同步")
    return 0


if __name__ == "__main__":
    sys.exit(main())
