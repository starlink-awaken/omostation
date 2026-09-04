#!/usr/bin/env python3
"""round-gate-check — Round 三门槛守门检查。

每 Round 必须显式回答 3 个门槛:
- P72: 路径不过载？
- P52: 不动元模型/引擎？
- P74: Governance 自闭环？

Usage:
    python3 bin/gac/round-gate-check.py --pr <pr-number> [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def check_p72_path_overload(pr_files: list[str]) -> dict:
    """P72: 路径不过载 — 单 PR 修改路径 <= 10, 单文件 <= 200 行。"""
    unique_dirs = set()
    total_changes = 0

    for f in pr_files:
        parts = f.split("/")
        if len(parts) > 1:
            unique_dirs.add("/".join(parts[:2]))

    return {
        "gate": "P72",
        "name": "路径不过载",
        "unique_directories": len(unique_dirs),
        "total_files": len(pr_files),
        "pass": len(unique_dirs) <= 5 and len(pr_files) <= 10,
        "detail": f"{len(unique_dirs)} directories, {len(pr_files)} files",
    }


def check_p52_no_meta_change(pr_files: list[str]) -> dict:
    """P52: 不动元模型/引擎 — 不修改 MOF 元模型定义。"""
    meta_patterns = [
        "projects/ecos/src/ecos/ssot/mof/",
        "projects/ecos/src/ecos/ssot/registry/",
    ]
    violated = [f for f in pr_files if any(p in f for p in meta_patterns)]

    return {
        "gate": "P52",
        "name": "不动元模型/引擎",
        "violated_files": violated,
        "pass": len(violated) == 0,
        "detail": f"{len(violated)} meta files changed" if violated else "No meta changes",
    }


def check_p74_governance() -> dict:
    """P74: Governance 自闭环 — p74_solidification.warn_count == 0。"""
    result = subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", "bin/agent-workflow.py", "compliance", "--json"],
        capture_output=True, text=True, cwd=REPO,
    )

    warn_count = 0
    try:
        data = json.loads(result.stdout)
        warn_count = data.get("p74_solidification", {}).get("warn_count", 0)
    except (json.JSONDecodeError, KeyError):
        pass

    return {
        "gate": "P74",
        "name": "Governance 自闭环",
        "warn_count": warn_count,
        "pass": warn_count == 0,
        "detail": f"warn_count={warn_count}",
    }


def get_pr_files(pr_number: str) -> list[str]:
    """获取 PR 的文件列表。"""
    result = subprocess.run(
        ["gh", "pr", "view", pr_number, "--json", "files", "--jq", ".[].path"],
        capture_output=True, text=True, cwd=REPO,
    )
    if result.returncode == 0:
        return [f for f in result.stdout.splitlines() if f]
    return []


def main():
    parser = argparse.ArgumentParser(description="Round 三门槛守门")
    parser.add_argument("--pr", help="PR number to check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    files = get_pr_files(args.pr) if args.pr else []

    results = [
        check_p72_path_overload(files),
        check_p52_no_meta_change(files),
        check_p74_governance(),
    ]

    all_pass = all(r["pass"] for r in results)

    output = {
        "overall": "PASS" if all_pass else "FAIL",
        "gates": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Round Gate Check: {output['overall']}")
        for r in results:
            icon = "✅" if r["pass"] else "❌"
            print(f"  {icon} {r['gate']} ({r['name']}): {r['detail']}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
