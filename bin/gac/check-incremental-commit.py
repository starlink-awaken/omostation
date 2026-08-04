#!/usr/bin/env python3
"""CR-P76-8-4-INCREMENTAL-COMMIT: 检查增量提交防丢失.

每 sub-task 完成立即 commit, 防 X-Plane clean worktree 丢失工作.
检查 git diff 中是否包含过多跨目录文件, 提示应增量提交。
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 单次提交建议的最大文件数
MAX_FILES_PER_COMMIT = 15
# 单次提交建议的最大跨目录数
MAX_DIRS_PER_COMMIT = 3


def get_changed_files() -> list:
    """获取已暂存和未暂存的变更文件列表。"""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    staged = [f for f in result.stdout.splitlines() if f.strip()]

    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    unstaged = [f for f in result.stdout.splitlines() if f.strip()]

    return staged, unstaged


def main() -> int:
    staged, unstaged = get_changed_files()
    violations = []

    # 检查暂存变更
    if len(staged) > MAX_FILES_PER_COMMIT:
        dirs = set()
        for f in staged:
            parts = f.split("/")
            if len(parts) >= 2:
                dirs.add("/".join(parts[:2]))
        dir_count = len(dirs)
        top_dir_count = len(set(f.split("/")[0] for f in staged if "/" in f))
        violations.append(
            f"  staged: {len(staged)} 个文件, {dir_count} 个目录, "
            f"跨 {top_dir_count} 个顶级目录 "
            f"(建议 ≤{MAX_FILES_PER_COMMIT} 文件/≤{MAX_DIRS_PER_COMMIT} 目录)"
        )

    # 同时有 staged 和 unstaged 变更 — 提示增量提交
    if staged and unstaged:
        violations.append(
            f"  staged {len(staged)} 个文件 + unstaged {len(unstaged)} 个文件 — "
            "建议先提交已暂存变更, 再处理未暂存变更"
        )

    if violations:
        print(f"WARN 增量提交建议 ({len(violations)} 项):")
        for v in violations:
            print(v)
        return 0  # advisory only

    print("OK 增量提交模式良好")
    return 0


if __name__ == "__main__":
    sys.exit(main())
