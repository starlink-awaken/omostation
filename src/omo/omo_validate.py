"""omo validate — .omo 目录验证工具集.

从 bin/omo-validate 迁移.

提供:
  - completeness: 验证 .omo 目录完整性 (M1 治理节点覆盖)
  - references: 验证关键文件引用完整性
  - state: 验证状态一致性 (stale 检测)
  - all: 执行全部验证
"""

from __future__ import annotations

import argparse
import time

from omo.omo_paths import OMO_ROOT, PROJECTS_DIR
from omo.omo_shared import load_yaml

M1_DIR = PROJECTS_DIR / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"

EXPECTED_DIRS = {
    "_archive": "归档",
    "_control": "控制面",
    "_delivery": "交付面",
    "_knowledge": "知识面",
    "_truth": "事实面",
    "change-log": "变更日志",
    "cron": "定时任务",
    "debt": "技术债务",
    "evidence": "证据",
    "goals": "目标",
    "standards": "标准",
    "state": "状态",
    "tasks": "任务",
    "tests": "测试",
    "workers": "工作者",
}

KEY_FILES = [
    "state/system.yaml",
    "state/health.yaml",
    "goals/current.yaml",
    "_truth/INDEX.md",
    "_truth/registry/mof-capabilities.yaml",
    "standards/omo-governance-surfaces.md",
]


def load_m1_governance() -> list[dict]:
    """加载所有 M1 治理节点."""
    nodes: list[dict] = []
    gov_dir = M1_DIR / "governance"
    if not gov_dir.exists():
        return nodes
    for yaml_file in gov_dir.glob("GOV-OMO-*.yaml"):
        try:
            data = load_yaml(yaml_file)
            if isinstance(data, dict) and "id" in data:
                nodes.append(data)
        except Exception:
            pass
    return nodes


def validate_completeness() -> dict:
    """验证 .omo 目录完整性."""
    gov_nodes = load_m1_governance()

    covered: set[str] = set()
    for node in gov_nodes:
        path = node.get("path", "")
        if path.startswith(".omo/"):
            dir_name = path.replace(".omo/", "").rstrip("/")
            covered.add(dir_name)

    missing = set(EXPECTED_DIRS.keys()) - covered

    return {
        "total_dirs": len(EXPECTED_DIRS),
        "covered": len(covered),
        "missing": list(missing),
        "coverage_pct": len(covered) / len(EXPECTED_DIRS) * 100 if EXPECTED_DIRS else 0,
    }


def validate_references() -> list[dict]:
    """验证引用完整性."""
    issues: list[dict] = []

    for f in KEY_FILES:
        path = OMO_ROOT / f
        if not path.exists():
            issues.append(
                {
                    "type": "missing_file",
                    "severity": "high",
                    "message": f"Key file missing: {f}",
                }
            )

    return issues


def validate_state() -> list[dict]:
    """验证状态一致性."""
    issues: list[dict] = []

    system_yaml = OMO_ROOT / "state" / "system.yaml"
    if system_yaml.exists():
        mtime = system_yaml.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        if age_hours > 24:
            issues.append(
                {
                    "type": "stale_state",
                    "severity": "medium",
                    "message": f"system.yaml is {age_hours:.1f}h old (>24h)",
                }
            )

    return issues


def cmd_completeness() -> int:
    """验证 .omo 目录完整性."""
    result = validate_completeness()
    print("OMO 完整性验证\n")
    print(f"总目录: {result['total_dirs']}")
    print(f"已覆盖: {result['covered']}")
    print(f"覆盖率: {result['coverage_pct']:.1f}%")
    if result["missing"]:
        print("\n未覆盖:")
        for m in result["missing"]:
            print(f"  [MISSING] {m}")
    return 0


def cmd_references() -> int:
    """验证引用完整性."""
    issues = validate_references()
    print("OMO 引用验证\n")
    if not issues:
        print("All key files exist.")
    else:
        for issue in issues:
            print(f"[{issue['severity'].upper()}] {issue['message']}")
    return 0


def cmd_state() -> int:
    """验证状态一致性."""
    issues = validate_state()
    print("OMO 状态验证\n")
    if not issues:
        print("State is fresh.")
    else:
        for issue in issues:
            print(f"[{issue['severity'].upper()}] {issue['message']}")
    return 0


def cmd_all() -> int:
    """执行全部验证."""
    print("OMO 全面验证\n")

    result = validate_completeness()
    print(
        f"完整性: {result['covered']}/{result['total_dirs']} ({result['coverage_pct']:.1f}%)"
    )
    if result["missing"]:
        print(f"  未覆盖: {', '.join(result['missing'])}")

    issues = validate_references()
    print(f"\n引用: {len(issues)} issues")

    state_issues = validate_state()
    print(f"状态: {len(state_issues)} issues")

    total_issues = len(issues) + len(state_issues)
    if total_issues == 0:
        print("\nAll checks passed.")
    else:
        print(f"\n{total_issues} issues found.")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo validate",
        description="OMO 目录验证工具集",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "completeness",
        help="验证 .omo 目录完整性 (M1 治理节点覆盖)",
    )
    sub.add_parser(
        "references",
        help="验证关键文件引用完整性",
    )
    sub.add_parser(
        "state",
        help="验证状态一致性 (stale 检测)",
    )
    sub.add_parser(
        "all",
        help="执行全部验证",
    )

    args = parser.parse_args(argv)

    if args.command == "completeness":
        return cmd_completeness()
    if args.command == "references":
        return cmd_references()
    if args.command == "state":
        return cmd_state()
    if args.command == "all":
        return cmd_all()

    parser.print_help()
    return 1
