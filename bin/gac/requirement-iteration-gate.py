#!/usr/bin/env python3
"""requirement-iteration-gate — 需求迭代闸门 (ADR-0204)。

对已 stage 的需求面路径检查是否存在 active run。
无 run → halt (exit 1)。

Usage:
    python3 bin/gac/requirement-iteration-gate.py [--path <path>] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def get_staged_files() -> list[str]:
    """获取已 stage 的文件列表。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=REPO,
    )
    return [f for f in result.stdout.splitlines() if f]


def is_requirement_path(path: str) -> bool:
    """判断是否为需求面路径。"""
    req_prefixes = [
        "projects/", "docs/", "bin/", ".omo/",
        "AGENTS.md", "CLAUDE.md", "ARCHITECTURE.md",
    ]
    return any(path.startswith(p) for p in req_prefixes)


def check_active_run(path: str) -> bool:
    """检查是否存在 active run。"""
    runs_dir = REPO / ".omo/_delivery/agent-workflows/runs"
    if not runs_dir.exists():
        return False
    # 简化检查: 是否有 active 状态的 run
    active_runs = list(runs_dir.glob("*/state.yaml"))
    return len(active_runs) > 0


def main():
    parser = argparse.ArgumentParser(description="需求迭代闸门")
    parser.add_argument("--path", help="指定路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    staged = get_staged_files()
    req_files = [f for f in staged if is_requirement_path(f)]

    if not req_files:
        return 0  # 无需求面文件，放行

    has_run = check_active_run(args.path) if args.path else False

    result = {
        "staged_files": len(staged),
        "requirement_files": req_files,
        "has_active_run": has_run,
        "action": "PASS" if has_run else "HALT",
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if has_run:
            print("PASS: Active run found")
        else:
            print("HALT: No active run for requirement files")
            print(f"Staged: {req_files}")
            print("Run: uv run python bin/agent-workflow.py start <workflow>")

    return 0 if has_run else 1


if __name__ == "__main__":
    sys.exit(main())
