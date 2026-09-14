#!/usr/bin/env python3
"""ecosystem-doctor — 生态统一巡检入口。

统一检查 Skills/Workflows/Scripts/Governance 生态健康度。

Usage:
    python3 bin/gac/ecosystem-doctor.py [--scope <skills|workflows|scripts|governance|all>] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def check_skills() -> dict:
    """检查 Skills 健康度."""
    skills_dir = REPO / ".agents/skills"
    if not skills_dir.exists():
        return {"status": "missing", "count": 0}

    skills = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        has_skill_md = skill_md.exists()
        skills.append({
            "name": skill_dir.name,
            "has_skill_md": has_skill_md,
        })

    with_md = sum(1 for s in skills if s["has_skill_md"])

    return {
        "status": "ok" if with_md == len(skills) else "warn",
        "total": len(skills),
        "with_skill_md": with_md,
        "skills": skills,
    }


def check_workflows() -> dict:
    """检查 Workflows 健康度."""
    runs_dir = REPO / ".omo/_delivery/agent-workflows/runs"
    workflows_dir = REPO / ".omo/_truth/registry/agent-workflows/workflows"

    workflow_files = list(workflows_dir.glob("*.yaml")) if workflows_dir.exists() else []

    # 统计 runs
    ok_count = 0
    blocked_count = 0
    failed_count = 0
    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            state_file = run_dir / "state.yaml"
            if state_file.exists():
                content = state_file.read_text()
                if "status: ok" in content:
                    ok_count += 1
                elif "status: blocked" in content:
                    blocked_count += 1
                elif "status: failed" in content:
                    failed_count += 1

    total_runs = ok_count + blocked_count + failed_count

    return {
        "status": "ok" if blocked_count < 10 else "warn",
        "registered_workflows": len(workflow_files),
        "total_runs": total_runs,
        "runs": {"ok": ok_count, "blocked": blocked_count, "failed": failed_count},
    }


def check_scripts() -> dict:
    """检查 Scripts 注册健康度."""
    registry_dir = REPO / "bin/_registry/scripts"
    bin_dir = REPO / "bin"

    # 统计已注册脚本
    registered = set()
    for yaml_file in registry_dir.rglob("*.yaml"):
        data = yaml_file.read_text()
        if "id:" in data:
            registered.add(yaml_file.stem)

    # 统计实际脚本
    actual = set()
    for ext in ("*.py", "*.sh"):
        for f in bin_dir.rglob(ext):
            if "_archive" not in str(f) and "__pycache__" not in str(f):
                actual.add(f.stem)

    # 未注册的脚本 (排除测试和库)
    unregistered = actual - registered
    # 过滤掉明显不需要注册的
    exclude_patterns = {"conftest", "test_", "__init__", "setup"}
    unregistered = {
        s for s in unregistered
        if not any(p in s for p in exclude_patterns)
    }

    return {
        "status": "ok" if len(unregistered) < 20 else "warn",
        "registered": len(registered),
        "actual": len(actual),
        "unregistered_count": len(unregistered),
        "unregistered_sample": sorted(unregistered)[:10],
    }


def check_governance() -> dict:
    """检查 Governance 注册表健康度."""
    registry_dir = REPO / ".omo/_truth/registry"
    if not registry_dir.exists():
        return {"status": "missing"}

    registries = list(registry_dir.glob("*.yaml"))
    # 检查关键注册表是否存在
    critical = [
        "governance-checks.yaml",
        "harness-policy.yaml",
        "ci-surfaces.yaml",
    ]
    missing = [f for f in critical if not (registry_dir / f).exists()]

    return {
        "status": "ok" if not missing else "warn",
        "total_registries": len(registries),
        "missing_critical": missing,
    }


def main():
    parser = argparse.ArgumentParser(description="生态统一巡检")
    parser.add_argument(
        "--scope",
        choices=["skills", "workflows", "scripts", "governance", "all"],
        default="all",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = {}

    if args.scope in ("skills", "all"):
        results["skills"] = check_skills()
    if args.scope in ("workflows", "all"):
        results["workflows"] = check_workflows()
    if args.scope in ("scripts", "all"):
        results["scripts"] = check_scripts()
    if args.scope in ("governance", "all"):
        results["governance"] = check_governance()

    # 综合评分
    statuses = [v.get("status", "unknown") for v in results.values()]
    overall = "HEALTHY" if all(s == "ok" for s in statuses) else "DEGRADED"

    output = {
        "overall": overall,
        "scopes": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Ecosystem Doctor: {overall}")
        for scope, data in results.items():
            icon = "✅" if data.get("status") == "ok" else "⚠️"
            print(f"  {icon} {scope}: {data.get('status', '?')}")

    return 0 if overall == "HEALTHY" else 1


if __name__ == "__main__":
    sys.exit(main())
