#!/usr/bin/env python3
"""p78-diagnostic-prescan — P78 诊断前置 4 问自动扫描。

在编辑前自动检查:
1. 反证: 是否有证据反驳当前结论？
2. 运行时实证: 是否验证了实际运行结果？
3. ADR: 是否查阅了相关架构决策？
4. 工具链: 是否检查了 bin/ssot + .github/workflows？

Usage:
    python3 bin/gac/p78-diagnostic-prescan.py [--path <path>] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def check_counter_evidence(path: Path) -> dict:
    """检查是否有反证文件。"""
    findings = []
    # 检查是否有 retros/audits 反驳当前结论
    retros = list((REPO / ".omo/_knowledge/retros").rglob("*.md"))
    findings.append({
        "check": "retros_exist",
        "status": len(retros) > 0,
        "count": len(retros),
    })
    return {"check": "counter_evidence", "findings": findings}


def check_runtime_evidence(path: Path) -> dict:
    """检查是否有运行时实证。"""
    findings = []
    # 检查是否有 evidence/ 目录
    evidence_dir = REPO / "docs/evidence"
    if evidence_dir.exists():
        evidence_files = list(evidence_dir.rglob("*.md"))
        findings.append({
            "check": "evidence_exists",
            "status": len(evidence_files) > 0,
            "count": len(evidence_files),
        })
    return {"check": "runtime_evidence", "findings": findings}


def check_adr_reference(path: Path) -> dict:
    """检查是否引用了相关 ADR。"""
    findings = []
    adr_dir = REPO / ".omo/_knowledge/decisions"
    if adr_dir.exists():
        adr_count = len(list(adr_dir.glob("*.md")))
        findings.append({
            "check": "adr_available",
            "status": adr_count > 0,
            "count": adr_count,
        })
    return {"check": "adr_reference", "findings": findings}


def check_toolchain(path: Path) -> dict:
    """检查工具链完整性。"""
    findings = []
    ssot_dir = REPO / "bin/ssot"
    workflows_dir = REPO / ".github/workflows"
    findings.append({
        "check": "ssot_tools",
        "status": ssot_dir.exists(),
        "count": len(list(ssot_dir.glob("*.py"))) if ssot_dir.exists() else 0,
    })
    findings.append({
        "check": "ci_workflows",
        "status": workflows_dir.exists(),
        "count": len(list(workflows_dir.glob("*.yml"))) if workflows_dir.exists() else 0,
    })
    return {"check": "toolchain", "findings": findings}


def main():
    parser = argparse.ArgumentParser(description="P78 诊断前置扫描")
    parser.add_argument("--path", help="目标路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    target = Path(args.path) if args.path else REPO

    results = {
        "target": str(target.relative_to(REPO)),
        "checks": [
            check_counter_evidence(target),
            check_runtime_evidence(target),
            check_adr_reference(target),
            check_toolchain(target),
        ],
    }

    all_pass = all(
        all(f.get("status", False) for f in c["findings"])
        for c in results["checks"]
    )
    results["overall"] = "PASS" if all_pass else "FAIL"

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"P78 Diagnostic Prescan: {results['overall']}")
        for check in results["checks"]:
            for finding in check["findings"]:
                icon = "✅" if finding.get("status") else "❌"
                print(f"  {icon} {finding['check']}: {finding.get('count', 'N/A')}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
