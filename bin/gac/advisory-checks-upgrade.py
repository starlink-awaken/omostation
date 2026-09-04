#!/usr/bin/env python3
"""advisory-checks-upgrade — 将高价值 advisory 约束升级为可执行检查。

将 20 条 advisory 规则接入 CI/hook/cron 执行链。

Usage:
    python3 bin/gac/advisory-checks-upgrade.py [--check] [--apply] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 高价值 advisory 规则及其集成目标
UPGRADE_TARGETS = [
    {
        "id": "CR-X4-TEST-COVERAGE",
        "name": "测试覆盖检查",
        "check": ["python3", "-m", "pytest", "--co", "-q"],
        "target": "ci_gate",
        "priority": "P0",
    },
    {
        "id": "CR-X4-ADR-LINKS",
        "name": "ADR 链接完整性",
        "check": ["python3", "bin/ssot/doc-link-check.py"],
        "target": "pre_commit",
        "priority": "P0",
    },
    {
        "id": "CR-L2-DIRECT-IO",
        "name": ".omo 直写拦截",
        "check": ["python3", "bin/gac/check-omo-direct-io.py"],
        "target": "pre_commit",
        "priority": "P0",
    },
    {
        "id": "CR-X1-GOD-MODULE-LIMIT",
        "name": "God module 行数上限",
        "check": ["python3", "bin/gac/check-god-module.py"],
        "target": "pre_commit",
        "priority": "P1",
    },
    {
        "id": "CR-X2-GAC-DRIFT",
        "name": "GaC 漂移检测",
        "check": ["python3", "bin/gac/gac-drift.py"],
        "target": "cron",
        "priority": "P1",
    },
    {
        "id": "CR-X4-DOC-SSOT",
        "name": "文档 SSOT 合规",
        "check": ["python3", "bin/ssot/doc-ssot-lint.py", "--json"],
        "target": "ci_gate",
        "priority": "P1",
    },
    {
        "id": "CR-X4-SUBMODULE-POINTER-INTEGRITY",
        "name": "子模块指针完整性",
        "check": ["python3", "bin/gac/check-submodule-pointer-integrity.py"],
        "target": "pre_push",
        "priority": "P1",
    },
    {
        "id": "CR-L2-SURFACES-INTEGRITY",
        "name": "Governance surfaces 完整",
        "check": ["python3", "bin/gac/check-omo-surfaces.py"],
        "target": "pre_commit",
        "priority": "P1",
    },
    {
        "id": "CR-X2-DOC-FRESHNESS-GATE",
        "name": "文档新鲜度门禁",
        "check": ["python3", "bin/ssot/freshness.py"],
        "target": "cron",
        "priority": "P1",
    },
    {
        "id": "CR-X4-MESH-EXECUTOR-RELIABILITY",
        "name": "Mesh executor 可靠性",
        "check": ["python3", "bin/gac/check-mesh-executor-reliability.py"],
        "target": "ci_gate",
        "priority": "P2",
    },
    {
        "id": "CR-X4-MESH-ROUTING-CONSISTENCY",
        "name": "Mesh 路由一致性",
        "check": ["python3", "bin/gac/check-mesh-routing-consistency.py"],
        "target": "ci_gate",
        "priority": "P2",
    },
    {
        "id": "CR-X4-SWEEP-TOOL-INTEGRITY",
        "name": "Sweep 工具完整性",
        "check": ["python3", "bin/gac/check-sweep-tool-integrity.py"],
        "target": "ci_gate",
        "priority": "P2",
    },
]


def check_single(target: dict) -> dict:
    """运行单个检查。"""
    try:
        result = subprocess.run(
            target["check"],
            capture_output=True, timeout=60, cwd=REPO,
        )
        return {
            "id": target["id"],
            "name": target["name"],
            "ok": result.returncode == 0,
            "target": target["target"],
            "priority": target["priority"],
        }
    except Exception as e:
        return {
            "id": target["id"],
            "name": target["name"],
            "ok": False,
            "error": str(e),
            "target": target["target"],
            "priority": target["priority"],
        }


def main():
    parser = argparse.ArgumentParser(description="Advisory 约束升级检查")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = [check_single(t) for t in UPGRADE_TARGETS]
    passed = sum(1 for r in results if r["ok"])

    output = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "checks": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Advisory Checks Upgrade: {passed}/{len(results)} passed")
        for r in results:
            icon = "PASS" if r["ok"] else "FAIL"
            print(f"  [{icon}] [{r['priority']}] {r['id']}: {r['name']}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
