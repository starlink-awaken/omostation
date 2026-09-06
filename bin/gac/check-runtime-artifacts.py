#!/usr/bin/env python3
"""
机制 1 (2026-09-05): 运行时产物黑名单检测 — 拦截 .sqlite/.db/.pyc/.omo/locks 等误提交.

使用:
  python bin/gac/check-runtime-artifacts.py           # 检测 staged 新增文件
  python bin/gac/check-runtime-artifacts.py --staged  # 同上 (pre-commit 模式)
  python bin/gac/check-runtime-artifacts.py --all     # 检测所有 tracked 文件 (CI 模式)

退出码:
  0 = 无违规
  1 = 发现运行时产物被 staged/tracked
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# 运行时产物黑名单 — suffix / filename / prefix 三元组
BLACKLIST_SUFFIXES = {
    ".sqlite", ".sqlite3", ".db", ".db-shm", ".db-wal",
    ".pyc", ".pyo", ".so", ".egg-info",
    ".log", ".pid", ".bak",
}

BLACKLIST_FILENAMES = {
    ".DS_Store", "Thumbs.db", "desktop.ini",
    ".omc",  # OMC runtime state dir
}

BLACKLIST_PREFIXES = (
    ".omo/locks/",
    ".omo/evidence/",
    ".omo/state/",
    ".omo/_derived/",
    ".omo/capabilities/",
    ".omo/tests/",
    ".omo/workers/",
    ".omo/plans/",
    ".omo/run-continuation/",
    ".omo/_delivery/",
    ".omo/_control/",
    ".omo/_knowledge/evolution-proposals/",
    ".omo/_knowledge/sediment/",
    ".omo/_knowledge/decision-proposals/",
    ".omo/_knowledge/workflow-mesh/",
    ".omo/reports/",
    ".omo/_archive/",
    ".omo/autopilot/",
    ".omo/change-log/",
    ".omo/cron/",
    ".artifacts/",
    "__pycache__/",
    ".venv/",
    ".mimocode/",
    ".codebuddy/",
    ".openclaude/",
    ".claude/",
    ".cursor/",
    ".vscode/",
    ".idea/",
    ".subtrees/",
    ".codebase-memory/",
    "runtime/",
    "_derivation_logs/",
    "agent-runtime/",
    ".benchmarks/",
    ".deepeval/",
    ".kb/",
    ".omc/notepads/",
    ".omc/logs/",
    "bin/.omo/",
)


def get_staged_files() -> list[str]:
    """获取 staged 新增/修改文件."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.splitlines() if f]


def get_all_tracked() -> list[str]:
    """获取所有 tracked 文件."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.splitlines()


def is_runtime_artifact(path: str) -> tuple[bool, str]:
    """检测文件是否为运行时产物. 返回 (is_artifact, reason)."""
    name = os.path.basename(path)

    # 检查 suffix
    suffix = Path(path).suffix.lower()
    if suffix in BLACKLIST_SUFFIXES:
        return True, f"黑名单后缀: {suffix}"

    # 检查 filename
    if name in BLACKLIST_FILENAMES:
        return True, f"黑名单文件名: {name}"

    # 检查 prefix
    for prefix in BLACKLIST_PREFIXES:
        if path.startswith(prefix):
            return True, f"黑名单前缀: {prefix}"

    return False, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="运行时产物黑名单检测")
    parser.add_argument("--all", action="store_true", help="检测所有 tracked 文件 (CI 模式)")
    parser.add_argument("--staged", action="store_true", help="检测 staged 文件 (pre-commit 模式)")
    args = parser.parse_args()

    if args.all:
        files = get_all_tracked()
    else:
        files = get_staged_files()

    violations: list[tuple[str, str]] = []
    for f in files:
        is_art, reason = is_runtime_artifact(f)
        if is_art:
            violations.append((f, reason))

    if violations:
        print(f"❌ 发现 {len(violations)} 个运行时产物被 staged/tracked:", file=sys.stderr)
        for path, reason in violations:
            print(f"   {path}  ({reason})", file=sys.stderr)
        print("\n修复: git rm --cached <file> + 追加到 .gitignore", file=sys.stderr)
        return 1

    print(f"✅ 无运行时产物违规 ({len(files)} 个文件已检查)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
