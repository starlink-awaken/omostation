#!/usr/bin/env python3
"""check-pr-lifecycle.py — PR 生命周期可见性检查 (ci_only).

识别 closed-without-merge 的 PR，交叉引用后续 PR 检测吸收关系。
标记涉及治理文件 (bin/gac/, .omo/, docs/) 但无吸收痕迹的 PR。

rule_id: CR-X4-PR-LIFECYCLE-VISIBILITY

用法:
    python3 bin/gac/check-pr-lifecycle.py              # 全量扫
    python3 bin/gac/check-pr-lifecycle.py --json       # JSON 输出
    python3 bin/gac/check-pr-lifecycle.py --days 30    # 最近 30 天
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

# 涉及治理面的路径前缀
GOVERNANCE_PREFIXES = ("bin/gac/", ".omo/", "docs/", "bin/ssot/", "projects/ecos/src/ecos/ssot/")


def _run_gh(args: list[str]) -> str:
    """Run gh CLI and return stdout."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def load_closed_prs(days: int = 14) -> list[dict]:
    """Load recently closed PRs via gh."""
    raw = _run_gh([
        "pr", "list",
        "--state", "closed",
        "--limit", "100",
        "--json", "number,title,body,mergedAt,closedAt,files,labels",
        "--search", f"closed:>={_days_ago(days)}",
    ])
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _days_ago(days: int) -> str:
    """Return ISO date string for N days ago."""
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


def load_merged_pr_numbers(days: int = 30) -> set[int]:
    """Load PR numbers that were actually merged (not just closed)."""
    raw = _run_gh([
        "pr", "list",
        "--state", "merged",
        "--limit", "200",
        "--json", "number",
        "--search", f"merged:>={_days_ago(days)}",
    ])
    if not raw:
        return set()
    try:
        return {pr["number"] for pr in json.loads(raw)}
    except (json.JSONDecodeError, KeyError):
        return set()


def detect_absorption(closed_pr: dict, merged_numbers: set[int], days: int) -> dict:
    """Check if a closed-without-merge PR was absorbed by a subsequent merged PR."""
    pr_number = closed_pr["number"]
    title = closed_pr.get("title", "")
    body = closed_pr.get("body", "") or ""

    # Get files changed by this closed PR
    files_raw = _run_gh([
        "pr", "str", str(pr_number),
        "--json", "files",
    ])
    closed_files: set[str] = set()
    if files_raw:
        try:
            pr_data = json.loads(files_raw)
            closed_files = {f["path"] for f in pr_data.get("files", [])}
        except (json.JSONDecodeError, KeyError):
            pass

    if not closed_files:
        return {"absorbed": False, "reason": "no_file_info"}

    # Check subsequent merged PRs for overlapping files
    for merged_num in sorted(merged_numbers):
        if merged_num <= pr_number:
            continue
        merged_raw = _run_gh([
            "pr", "str", str(merged_num),
            "--json", "files,title",
        ])
        if not merged_raw:
            continue
        try:
            merged_data = json.loads(merged_raw)
            merged_files = {f["path"] for f in merged_data.get("files", [])}
            overlap = closed_files & merged_files
            if overlap:
                return {
                    "absorbed": True,
                    "absorbed_by": merged_num,
                    "overlap_files": sorted(overlap),
                }
        except (json.JSONDecodeError, KeyError):
            continue

    return {"absorbed": False, "reason": "no_overlap_found"}


def check_pr_lifecycle(days: int = 14) -> dict:
    """Full PR lifecycle check."""
    closed_prs = load_closed_prs(days)
    merged_numbers = load_merged_pr_numbers(days * 2)

    results = []
    governance_without_absorption = []

    for pr in closed_prs:
        merged_at = pr.get("mergedAt")
        if merged_at:
            continue  # PR was merged, skip

        pr_number = pr["number"]
        title = pr.get("title", "")
        closed_at = pr.get("closedAt", "")

        absorption = detect_absorption(pr, merged_numbers, days)

        entry = {
            "number": pr_number,
            "title": title,
            "closed_at": closed_at,
            "absorbed": absorption.get("absorbed", False),
            "absorbed_by": absorption.get("absorbed_by"),
            "overlap_files": absorption.get("overlap_files", []),
        }
        results.append(entry)

        # Check if涉及治理文件但无吸收
        if not absorption.get("absorbed"):
            files_raw = _run_gh([
                "pr", "str", str(pr_number),
                "--json", "files",
            ])
            if files_raw:
                try:
                    pr_data = json.loads(files_raw)
                    has_gov_files = any(
                        f["path"].startswith(GOVERNANCE_PREFIXES)
                        for f in pr_data.get("files", [])
                    )
                    if has_gov_files:
                        governance_without_absorption.append(entry)
                except (json.JSONDecodeError, KeyError):
                    pass

    return {
        "period_days": days,
        "total_closed_without_merge": len(results),
        "absorbed": [r for r in results if r["absorbed"]],
        "not_absorbed": [r for r in results if not r["absorbed"]],
        "governance_without_absorption": governance_without_absorption,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PR 生命周期可见性检查")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--days", type=int, default=14, help="扫描天数 (default: 14)")
    args = parser.parse_args()

    result = check_pr_lifecycle(args.days)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=== PR 生命周期可见性检查 ===\n")
        print(f"扫描周期: 最近 {result['period_days']} 天")
        print(f"Closed-without-merge PR 数: {result['total_closed_without_merge']}")

        if result["absorbed"]:
            print(f"\n已吸收 ({len(result['absorbed'])}):")
            for r in result["absorbed"]:
                print(f"  #{r['number']} {r['title']} -> absorbed by #{r['absorbed_by']}")
                if r["overlap_files"]:
                    print(f"    重叠文件: {r['overlap_files'][:3]}")

        if result["not_absorbed"]:
            print(f"\n未吸收 ({len(result['not_absorbed'])}):")
            for r in result["not_absorbed"]:
                print(f"  #{r['number']} {r['title']} (closed {r['closed_at']})")

        if result["governance_without_absorption"]:
            print(f"\n治理文件 PR 未吸收 ({len(result['governance_without_absorption'])}):")
            for r in result["governance_without_absorption"]:
                print(f"  #{r['number']} {r['title']}")

        has_issues = bool(result["governance_without_absorption"])
        print(f"\nTotal: {len(result['governance_without_absorption'])} governance PRs without absorption")
        return 1 if has_issues else 0

    return 1 if result["governance_without_absorption"] else 0


if __name__ == "__main__":
    sys.exit(main())
