#!/usr/bin/env python3
"""gitlink-drift-protect — 子模块指针漂移检测与自动修复。

检测子模块指针漂移 (本地超前于追踪 commit) 并:
1. 尝试自动 fast-forward push
2. 如果无法 fast-forward，报告需人工介入
3. 记录漂移指纹到 gate-known-debt

Usage:
    python3 bin/gac/gitlink-drift-protect.py [--fix] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def get_submodule_status() -> list[dict]:
    """获取子模块状态。"""
    result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True, text=True, cwd=REPO,
    )

    submodules = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        # Parse: [+- ]<sha> <path> (<ref>)
        match = re.match(r'^([+\- ])([0-9a-f]+) (\S+)', line)
        if not match:
            continue

        prefix = match.group(1)
        sha = match.group(2)
        path = match.group(3)

        status = {
            "path": path,
            "sha": sha,
            "is_dirty": prefix == "+",
            "is_uninitialized": prefix == "-",
            "is_clean": prefix == " ",
        }
        submodules.append(status)

    return submodules


def get_ahead_count(path: Path) -> int:
    """获取本地超前于 origin/main 的 commit 数。"""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"origin/main..HEAD"],
            capture_output=True, text=True, cwd=path,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def can_fast_forward(path: Path) -> bool:
    """检查是否可以 fast-forward push。"""
    try:
        # 先 fetch
        subprocess.run(
            ["git", "fetch", "origin"],
            capture_output=True, timeout=30, cwd=path,
        )
        # 检查是否可以 fast-forward
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
            capture_output=True, cwd=path,
        )
        return result.returncode == 0
    except Exception:
        return False


def try_auto_push(path: Path) -> dict:
    """尝试自动推送。"""
    result = {"pushed": False, "error": None}

    if not can_fast_forward(path):
        result["error"] = "Cannot fast-forward, manual intervention needed"
        return result

    try:
        push_result = subprocess.run(
            ["git", "push", "origin", "HEAD:main"],
            capture_output=True, text=True, timeout=60, cwd=path,
        )
        if push_result.returncode == 0:
            result["pushed"] = True
        else:
            result["error"] = push_result.stderr[:200]
    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Gitlink 漂移防护")
    parser.add_argument("--fix", action="store_true", help="尝试自动修复")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    submodules = get_submodule_status()
    drifts = []
    clean = []
    uninitialized = []

    for sub in submodules:
        path = REPO / sub["path"]

        if sub["is_uninitialized"]:
            uninitialized.append(sub)
            continue

        if not sub["is_dirty"]:
            clean.append(sub)
            continue

        # 漂移检测
        ahead = get_ahead_count(path)
        sub["ahead_commits"] = ahead
        sub["branch"] = get_branch(path)

        if args.fix:
            sub["push_result"] = try_auto_push(path)

        drifts.append(sub)

    output = {
        "total": len(submodules),
        "clean": len(clean),
        "drifted": len(drifts),
        "uninitialized": len(uninitialized),
        "drifts": drifts,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Gitlink Drift Protect")
        print(f"  Total: {len(submodules)} | Clean: {len(clean)} | Drifted: {len(drifts)} | Uninit: {len(uninitialized)}")

        if drifts:
            print(f"\n  Drifted submodules:")
            for d in drifts:
                push_status = ""
                if args.fix:
                    push_status = " [PUSHED]" if d.get("push_result", {}).get("pushed") else f" [FAIL: {d.get('push_result', {}).get('error', '?')}]"
                print(f"    ⚠️ {d['path']}: +{d.get('ahead_commits', '?')} commits ({d.get('branch', '?')}){push_status}")

        if uninitialized:
            print(f"\n  Uninitialized:")
            for u in uninitialized:
                print(f"    ❌ {u['path']}")

    return 1 if drifts or uninitialized else 0


def get_branch(path: Path) -> str:
    """获取当前分支名。"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=path,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "?"


if __name__ == "__main__":
    sys.exit(main())
