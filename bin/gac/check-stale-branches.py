#!/usr/bin/env python3
"""check-stale-branches.py — 检测陈旧分支

BET-Y1Q4-T10-148 (repo hygiene): 扫描 git 分支，检测超过 TTL 未更新的
非受保护分支，标记 warning 并建议清理。

用法:
  python3 bin/gac/check-stale-branches.py
  python3 bin/gac/check-stale-branches.py --json
  python3 bin/gac/check-stale-branches.py --workspace /path/to/repo
  python3 bin/gac/check-stale-branches.py --ttl-days 14
  python3 bin/gac/check-stale-branches.py --protected-branches main,develop
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

DEFAULT_TTL_DAYS = 30
DEFAULT_PROTECTED = {"main", "master", "develop", "release"}


def get_workspace() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print("ERROR: 不在 git 仓库中", file=sys.stderr)
        sys.exit(1)


def list_branches(workspace: Path) -> List[Dict]:
    """列出所有本地分支及其最后提交时间"""
    branches = []
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "refs/heads/",
             "--format=%(refname:short)|%(committerdate:unix)|%(subject)"],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
    except subprocess.CalledProcessError:
        return branches

    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        name, ts_str, subject = parts[0].strip(), parts[1].strip(), parts[2].strip()
        try:
            ts = int(ts_str)
        except ValueError:
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        branches.append({
            "name": name,
            "last_commit_ts": ts,
            "last_commit_dt": dt.isoformat(),
            "subject": subject,
        })

    return branches


def check_branch_merged(workspace: Path, branch_name: str,
                         base_ref: str) -> bool:
    """检查分支是否已合并到 base"""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"{base_ref}..{branch_name}"],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError:
        return False


def run_checks(workspace: Path, ttl_days: int,
               protected: Set[str], base_ref: str) -> Dict:
    """执行所有检测"""
    branches = list_branches(workspace)
    now = datetime.now(timezone.utc)
    ttl_seconds = ttl_days * 86400

    results = {
        "total_branches": len(branches),
        "stale_count": 0,
        "merged_count": 0,
        "stale_branches": [],
        "merged_branches": [],
        "active_branches": 0,
    }

    for branch in branches:
        name = branch["name"]
        if name in protected:
            continue

        age_seconds = (now - datetime.fromtimestamp(
            branch["last_commit_ts"], tz=timezone.utc)).total_seconds()

        if age_seconds > ttl_seconds:
            results["stale_count"] += 1
            results["stale_branches"].append({
                "name": name,
                "last_commit": branch["last_commit_dt"],
                "age_days": round(age_seconds / 86400, 1),
                "subject": branch["subject"][:80],
                "level": "warning",
            })

        # Check if merged
        if check_branch_merged(workspace, name, base_ref):
            results["merged_count"] += 1
            results["merged_branches"].append({
                "name": name,
                "last_commit": branch["last_commit_dt"],
                "subject": branch["subject"][:80],
                "level": "warning",
            })

        if age_seconds <= ttl_seconds:
            results["active_branches"] += 1

    return results


def print_human_report(results: Dict) -> None:
    """人类可读报告"""
    print("=" * 60)
    print("  Stale Branches Report")
    print("=" * 60)
    print(f"\n  总分支数: {results['total_branches']}")
    print(f"  活跃分支: {results['active_branches']}")
    print(f"  陈旧分支: {results['stale_count']}")
    print(f"  已合并分支: {results['merged_count']}")
    print()

    if results["stale_branches"]:
        print(f"  ⚠️  陈旧分支 (超过 TTL):")
        for b in results["stale_branches"]:
            print(f"    {b['name']:40s} {b['age_days']:6.1f}d  "
                  f"{b['last_commit'][:10]}  {b['subject'][:40]}")
        print()

    if results["merged_branches"]:
        print(f"  ⚠️  已合并分支 (可清理):")
        for b in results["merged_branches"]:
            print(f"    {b['name']:40s} {b['last_commit'][:10]}  "
                  f"{b['subject'][:40]}")
        print()

    if not results["stale_branches"] and not results["merged_branches"]:
        print("  ✅ 无陈旧或已合并分支")


def main():
    parser = argparse.ArgumentParser(
        description="检测陈旧分支"
    )
    parser.add_argument("--workspace", type=str, default=None,
                        help="workspace 根目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--ttl-days", type=int, default=DEFAULT_TTL_DAYS,
                        help=f"TTL 天数 (默认: {DEFAULT_TTL_DAYS})")
    parser.add_argument("--protected-branches", type=str, default="",
                        help="受保护分支 (逗号分隔)")
    parser.add_argument("--base-branch", type=str, default="main",
                        help="base 分支 (默认: main)")
    args = parser.parse_args()

    workspace = Path(args.workspace) if args.workspace else get_workspace()
    protected = set(DEFAULT_PROTECTED)
    if args.protected_branches:
        protected = set(b.strip() for b in args.protected_branches.split(",")
                        if b.strip())

    base_ref = args.base_branch
    try:
        subprocess.run(
            ["git", "rev-parse", base_ref],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
    except subprocess.CalledProcessError:
        print(f"ERROR: 无法解析 base ref '{base_ref}'", file=sys.stderr)
        sys.exit(1)

    results = run_checks(workspace, args.ttl_days, protected, base_ref)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_human_report(results)


if __name__ == "__main__":
    main()
