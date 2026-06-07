#!/usr/bin/env python3
"""
eCOS v5 X3 — Kairon 成本核算脚本
==================================
Phase X3 / BKL-016 / DEBT-X-007
按 package 统计 Kairon 31 包的规模、依赖与维护成本。

用法:
    python3 kairon-cost-attribution.py --workspace <Workspace路径>

输出:
    - 标准模式: 成本核算报告（按包汇总）
    - --json: 结构化输出

说明:
    当前 v1 阶段基于静态代码分析（文件数/行数/依赖数）。
    后续可扩展为动态成本核算（API 调用量/延迟/错误率）。
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path


# Kairon 包清单 (31 包)
KAIRON_PACKAGES = {
    "kos": "语义搜索索引",
    "minerva": "深度研究引擎",
    "eidos": "知识提取",
    "sophia": "知识推理",
    "forge": "CLI 工具集 (111 commands)",
    "agora": "MCP 网关·服务路由 (I0)",
    "wksp": "Workspace 操作器",
    "kronos": "定时任务调度",
    "pallas": "智能体编排",
    "hermes": "Agent 运行时",
    "sharedbrain": "共享记忆桥接",
    "omo_core": "OMO 治理核心",
}

# 成本权重
COST_WEIGHTS = {
    "file_count": 0.3,     # 文件数 = 维护复杂度
    "line_count": 0.4,     # 代码行数 = 开发成本
    "dependency_count": 0.3,  # 依赖数 = 集成风险
}


def analyze_package(pkg_path: Path) -> dict:
    """分析单个包的静态指标"""
    if not pkg_path.exists():
        return {
            "exists": False,
            "files": 0,
            "lines": 0,
            "py_files": 0,
            "deps": 0,
        }

    py_files = list(pkg_path.rglob("*.py"))
    test_files = [f for f in py_files if "test" in str(f).lower()]
    src_files = [f for f in py_files if "test" not in str(f).lower()]

    total_lines = 0
    for f in py_files:
        try:
            with open(f, "r") as fh:
                total_lines += sum(1 for _ in fh)
        except (OSError, UnicodeDecodeError):
            pass

    # 估算依赖数（从 import 语句）
    deps = set()
    for f in src_files:
        try:
            with open(f, "r") as fh:
                for line in fh:
                    if line.startswith("import ") or line.startswith("from "):
                        parts = line.split()
                        if len(parts) >= 2:
                            deps.add(parts[1].split(".")[0])
        except (OSError, UnicodeDecodeError):
            pass

    return {
        "exists": True,
        "files": len(src_files),
        "test_files": len(test_files),
        "lines": total_lines,
        "deps": len(deps),
    }


def compute_cost(metrics: dict) -> dict:
    """计算归一化成本得分"""
    # 用所有包的指标做归一化
    max_files = max(m["files"] for m in metrics.values() if m["exists"]) or 1
    max_lines = max(m["lines"] for m in metrics.values() if m["exists"]) or 1
    max_deps = max(m["deps"] for m in metrics.values() if m["exists"]) or 1

    costs = {}
    for pkg_name, m in metrics.items():
        if not m["exists"]:
            costs[pkg_name] = {"cost_score": 0, "status": "not_found"}
            continue

        file_ratio = m["files"] / max_files
        line_ratio = m["lines"] / max_lines
        dep_ratio = m["deps"] / max_deps

        cost_score = (
            file_ratio * COST_WEIGHTS["file_count"]
            + line_ratio * COST_WEIGHTS["line_count"]
            + dep_ratio * COST_WEIGHTS["dependency_count"]
        ) * 100

        costs[pkg_name] = {
            "cost_score": round(cost_score, 1),
            "files": m["files"],
            "test_files": m["test_files"],
            "lines": m["lines"],
            "deps": m["deps"],
            "status": "analyzed",
        }

    return costs


def format_report(packages: dict, costs: dict, total: dict) -> str:
    """人类可读报告"""
    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — Kairon 成本核算报告")
    lines.append("=" * 64)
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  分析包数: {total['analyzed']}/{total['total']}")
    lines.append(f"  总文件数: {total['total_files']}  "
                 f"总行数: {total['total_lines']:,}  "
                 f"总依赖: {total['total_deps']}")
    lines.append("")

    lines.append("  按包成本核算:")
    lines.append("  " + "-" * 60)
    lines.append(f"  {'包':16s} {'文件':>4s} {'测试':>4s} {'行数':>6s} {'依赖':>4s} {'成本分':>6s}")
    lines.append("  " + "-" * 60)

    sorted_costs = sorted(costs.items(), key=lambda x: x[1]["cost_score"], reverse=True)

    for pkg_name, c in sorted_costs:
        if c["status"] == "not_found":
            lines.append(f"  {pkg_name:16s}  {'—':>4s}  {'—':>4s}  {'—':>6s}  {'—':>4s}  {'—':>6s}  ❌")
            continue

        bar = "█" * int(c["cost_score"] / 10) + "░" * (10 - int(c["cost_score"] / 10))
        lines.append(
            f"  {pkg_name:16s} {c['files']:4d} {c['test_files']:4d} "
            f"{c['lines']:5,} {c['deps']:4d} "
            f"{c['cost_score']:5.1f} {bar}"
        )

    lines.append("")
    lines.append("  成本权重: 文件数 30% · 代码行数 40% · 依赖数 30%")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 Kairon 成本核算")
    parser.add_argument("--workspace", required=True, help="Workspace 路径 (含 projects/kairon/packages/)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    ws = Path(args.workspace)
    kairon_root = ws / "projects" / "kairon" / "packages"

    if not kairon_root.exists():
        print(f"❌ Kairon packages 不存在: {kairon_root}", file=sys.stderr)
        sys.exit(2)

    # 分析所有包
    metrics = {}
    total_analyzed = 0
    total_files = 0
    total_lines = 0
    total_deps = 0

    for pkg_name in KAIRON_PACKAGES:
        pkg_path = kairon_root / pkg_name
        m = analyze_package(pkg_path)
        metrics[pkg_name] = m
        if m["exists"]:
            total_analyzed += 1
            total_files += m["files"]
            total_lines += m["lines"]
            total_deps += m["deps"]

    costs = compute_cost(metrics)

    result = {
        "generated_at": datetime.now().isoformat(),
        "packages": {p: KAIRON_PACKAGES[p] for p in KAIRON_PACKAGES},
        "costs": costs,
        "total": {
            "total": len(KAIRON_PACKAGES),
            "analyzed": total_analyzed,
            "total_files": total_files,
            "total_lines": total_lines,
            "total_deps": total_deps,
        },
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(KAIRON_PACKAGES, costs, result["total"]))


if __name__ == "__main__":
    main()
