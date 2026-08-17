#!/usr/bin/env python3
"""git-health-hook.py — git 健康守门 (Claude Code PreToolUse, advisory).

拦截 Edit|Write|MultiEdit, 检测主仓 core.bare 异常. 并发 agent (如 filter-repo)
可能把主仓 core.bare 改成 true, 导致 worktree claim 静默失败 (gac-worktree.sh
rev-parse 返回空, set -e 静默 exit). 此 hook 提前警告, 避免改完文件才发现
commit/worktree 全废.

机制: advisory (exit 0 + stderr 警告), 不阻塞工作流, 与 gac-hook-pre-edit.py
设计一致. exit 2 阻塞留给 GaC 类硬规则, git 健康只警告.

判据 (区分正常 bare clone vs 异常):
  - 正常 bare clone: core.bare=true 且**无 index** (bare 仓无 staging area)
  - 异常 core.bare=true: core.bare=true 且**有 index** (本有工作树, 被并发 agent
    误改; memory core-bare-anomaly 实证主仓 index 238KB + HEAD 含 ref:)
  注: --show-toplevel 在 core.bare=true 时 fatal 不可用, 改用 --absolute-git-dir
  (bare 状态下仍稳定返回 git-dir 绝对路径).

激活 (.claude/settings.json):
  {"hooks":{"PreToolUse":[{"matcher":"Edit|Write|MultiEdit","hooks":[
    {"type":"command","command":"python3 bin/ssot/git-health-hook.py","timeout":10}
  ]}]}}

输入 (stdin, Claude Code PreToolUse JSON): {"tool_name":"Edit","tool_input":{...}}
输出: exit 0 + stderr 警告 (异常时) 或 exit 0 静默 (正常). 永不 exit !=0.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TIMEOUT = 5  # git 调用超时, 秒


def _git(args: list[str]) -> str:
    """跑 git 命令, 失败返回空 (绝不抛, hook 必须 exit 0)."""
    try:
        p = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        return p.stdout.strip() if p.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def main() -> int:
    # 拿 git-dir 绝对路径 (--absolute-git-dir 在 core.bare=true 时仍稳定,
    # 不同于 --show-toplevel 会 fatal).
    git_dir = _git(["rev-parse", "--absolute-git-dir"])
    if not git_dir:
        return 0  # 非 git 目录, 放行

    bare = _git(["config", "core.bare"])
    if bare != "true":
        return 0  # 正常状态

    # core.bare=true, 区分正常 bare clone (无 index) vs 异常 (有 index 却 bare).
    # 正常 bare clone 无 staging area; 有 index 说明本有工作树, bare=true 是误改.
    if not (Path(git_dir) / "index").exists():
        return 0  # 正常 bare clone, 不告警

    # 异常: 有 index (工作树) 却 core.bare=true → 并发 agent 误操作
    sys.stderr.write(
        "⚠️ git 健康异常: 主仓 core.bare=true 却有工作树 index. "
        "这会让 worktree claim / commit 静默失败.\n"
        "  诊断: git config core.bare  → true\n"
        "  修复: git config core.bare false  (一行, 可逆)\n"
        "  验证: git rev-parse --show-toplevel  → 应返回主仓路径\n"
        "  根因: 并发 agent (如 filter-repo) 误改; 可能反复, 见 memory core-bare-anomaly\n"
    )
    return 0  # advisory, 不阻塞


if __name__ == "__main__":
    sys.exit(main())
