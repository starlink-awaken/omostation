#!/usr/bin/env python3
"""skill-recommender — 基于 diff 推荐适用的 skill/workflow。

分析当前变更 (git diff) 并推荐适用的 skill 和 workflow。

Usage:
    python3 bin/gac/skill-recommender.py [--base <ref>] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Skill 推荐规则: (路径模式, 推荐的 skill)
SKILL_RULES = [
    (r"projects/ecos/", "ecos-test-cycle"),
    (r"projects/omo/src/omo/governance", "governance-ssot-edit"),
    (r"projects/agora/", "bos-service-discovery"),
    (r"projects/cockpit/", "cockpit-cli-upgrade"),
    (r"AGENTS\.md|CLAUDE\.md", "workflow-silence-detection"),
    (r"bin/gac/", "governance-phase-orchestrator"),
    (r"bin/ssot/", "doc-ssot-lint"),
    (r"\.omo/_truth/registry/", "governance-ssot-edit"),
    (r"projects/.*/AGENTS\.md", "project-governance"),
    (r"docs/plans/", "bet-execution"),
    (r"\.github/workflows/", "ci-red-triage"),
]

# Workflow 推荐规则: (路径模式, 推荐的 workflow)
WORKFLOW_RULES = [
    (r"projects/.*/[a-zA-Z_]+\.py$", "project-code-change"),
    (r"projects/.*/.*\.md$", "project-doc-change"),
    (r"docs/plans/.*\.yaml$", "bet-execution"),
    (r"\.(omo|agents)/", "governance-state-mutation"),
    (r"bin/(gac|ssot)/", "governance-audit"),
    (r"projects/[^/]+/.*", "project-code-change"),
]


def get_changed_files(base: str = "origin/main") -> list[str]:
    """获取变更文件列表。"""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True, text=True, cwd=REPO,
    )
    if result.returncode != 0:
        # 尝试 staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=REPO,
        )
    return [f for f in result.stdout.splitlines() if f]


def recommend_skills(files: list[str]) -> list[dict]:
    """根据变更文件推荐 skill。"""
    recommendations = []
    seen = set()

    for pattern, skill in SKILL_RULES:
        for f in files:
            if re.search(pattern, f) and skill not in seen:
                seen.add(skill)
                recommendations.append({
                    "skill": skill,
                    "matched_pattern": pattern,
                    "matched_file": f,
                })

    return recommendations


def recommend_workflows(files: list[str]) -> list[dict]:
    """根据变更文件推荐 workflow。"""
    recommendations = []
    seen = set()

    for pattern, workflow in WORKFLOW_RULES:
        for f in files:
            if re.search(pattern, f) and workflow not in seen:
                seen.add(workflow)
                recommendations.append({
                    "workflow": workflow,
                    "matched_pattern": pattern,
                    "matched_file": f,
                })

    return recommendations


def main():
    parser = argparse.ArgumentParser(description="Skill/Workflow 推荐")
    parser.add_argument("--base", default="origin/main", help="对比基线")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    files = get_changed_files(args.base)

    if not files:
        print("No changes detected.")
        return 0

    skills = recommend_skills(files)
    workflows = recommend_workflows(files)

    output = {
        "changed_files": len(files),
        "skills": skills,
        "workflows": workflows,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Changed files: {len(files)}")
        if skills:
            print("\nRecommended Skills:")
            for s in skills:
                print(f"  - {s['skill']} (matched: {s['matched_file']})")
        if workflows:
            print("\nRecommended Workflows:")
            for w in workflows:
                print(f"  - {w['workflow']} (matched: {w['matched_file']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
