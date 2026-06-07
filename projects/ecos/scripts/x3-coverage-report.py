#!/usr/bin/env python3
"""
eCOS v5 X3 — X 轴覆盖率报告 v2.0
==================================
Phase X-Final / BKL-017
输出二值覆盖率 + 深度分级矩阵。

用法:
    python3 x3-coverage-report.py [--json]

深度分级:
    L0 = 不存在  L1 = 脚本存在  L2 = 功能完整  L3 = 集成自动
"""

import sys
import json
import argparse
from datetime import datetime

DOMAINS = ["CARDS", "OMO", "Kairon", "Vault", "域系统"]
DIMS = ["X1", "X2", "X3"]

# 二值覆盖率 (L1+ 算覆盖)
COVERAGE = {
    "CARDS":  {"X1": True,  "X2": True,  "X3": True},
    "OMO":    {"X1": True,  "X2": True,  "X3": True},
    "Kairon": {"X1": True,  "X2": True,  "X3": True},
    "Vault":  {"X1": True,  "X2": True,  "X3": True},
    "域系统":  {"X1": True,  "X2": True,  "X3": True},
}

# 深度分级 (L0-L3)
DEPTH = {
    "CARDS":  {"X1": 2, "X2": 2, "X3": 2},
    "OMO":    {"X1": 2, "X2": 2, "X3": 2},
    "Kairon": {"X1": 1, "X2": 2, "X3": 1},
    "Vault":  {"X1": 1, "X2": 2, "X3": 1},
    "域系统":  {"X1": 1, "X2": 1, "X3": 1},
}

# 限制标注
LIMITATIONS = {
    ("Vault", "X1"): "报告生成·非 card_history 写入",
    ("Kairon", "X1"): "包级审计·无专用 audit log (脚本自评 ⚠️)",
    ("Kairon", "X3"): "静态代码分析·非运行时调用量",
    ("域系统", "X1"): "STATE.md 借道·CARDS 间接审计",
    ("域系统", "X2"): "STATE.md 创建·一致性检查覆盖",
    ("域系统", "X3"): "文件统计·非任务级价值归因",
}

DEPTH_LABELS = {0: "❌ L0", 1: "⚠️ L1", 2: "✅ L2", 3: "🚀 L3"}

TARGETS = {"X1": 0.80, "X2": 0.80, "X3": 0.60, "overall": 0.73}


def compute_coverage() -> dict:
    results = {}
    for dim in DIMS:
        covered = sum(1 for d in DOMAINS if COVERAGE[d][dim])
        results[dim] = {
            "covered": covered, "total": len(DOMAINS),
            "ratio": covered / len(DOMAINS),
            "target": TARGETS[dim],
            "pass": covered / len(DOMAINS) >= TARGETS[dim],
        }
    overall = sum(r["covered"] for r in results.values()) / sum(r["total"] for r in results.values())
    results["overall"] = {"ratio": overall, "target": TARGETS["overall"], "pass": overall >= TARGETS["overall"]}
    return results


def compute_depth_stats() -> dict:
    stats = {}
    for dim in DIMS:
        depths = [DEPTH[d][dim] for d in DOMAINS]
        stats[dim] = {
            "L0": depths.count(0), "L1": depths.count(1),
            "L2": depths.count(2), "L3": depths.count(3),
            "L2_plus": sum(1 for x in depths if x >= 2),
        }
    all_depths = [DEPTH[d][dim] for d in DOMAINS for dim in DIMS]
    stats["overall"] = {
        "L0": all_depths.count(0), "L1": all_depths.count(1),
        "L2": all_depths.count(2), "L3": all_depths.count(3),
        "L2_plus": sum(1 for x in all_depths if x >= 2),
    }
    return stats


def format_report(results: dict, depth_stats: dict) -> str:
    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — X 轴覆盖率报告 v2.0 (含深度分级)")
    lines.append("=" * 64)
    lines.append(f"  生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 二值矩阵
    lines.append("  ┌──────────┬──────┬──────┬──────┐")
    lines.append("  │ 功能域   │  X1  │  X2  │  X3  │")
    lines.append("  ├──────────┼──────┼──────┼──────┤")
    for d in DOMAINS:
        x1 = "✅" if COVERAGE[d]["X1"] else "❌"
        x2 = "✅" if COVERAGE[d]["X2"] else "❌"
        x3 = "✅" if COVERAGE[d]["X3"] else "❌"
        lines.append(f"  │ {d:8s} │  {x1}  │  {x2}  │  {x3}  │")
    lines.append("  └──────────┴──────┴──────┴──────┘")
    lines.append("")

    # 深度矩阵
    lines.append("  ┌──────────┬──────────┬──────────┬──────────┐")
    lines.append("  │ 功能域   │    X1    │    X2    │    X3    │")
    lines.append("  ├──────────┼──────────┼──────────┼──────────┤")
    for d in DOMAINS:
        x1d = DEPTH_LABELS[DEPTH[d]["X1"]]
        x2d = DEPTH_LABELS[DEPTH[d]["X2"]]
        x3d = DEPTH_LABELS[DEPTH[d]["X3"]]
        lines.append(f"  │ {d:8s} │  {x1d:6s}  │  {x2d:6s}  │  {x3d:6s}  │")
    lines.append("  └──────────┴──────────┴──────────┴──────────┘")
    lines.append("")

    # 限制标注
    if LIMITATIONS:
        lines.append("  限制标注:")
        for (domain, dim), note in sorted(LIMITATIONS.items()):
            lines.append(f"    [{domain}][{dim}] {note}")
        lines.append("")

    # 深度统计
    lines.append("  深度分布:")
    lines.append("  " + "-" * 60)
    ds = depth_stats
    for dim in DIMS + ["overall"]:
        d = ds[dim]
        total = d["L0"] + d["L1"] + d["L2"] + d["L3"]
        l2_ratio = d["L2_plus"] / total * 100 if total > 0 else 0
        bar = "█" * int(l2_ratio / 10) + "░" * (10 - int(l2_ratio / 10))
        lines.append(f"  {dim:8s}  L0:{d['L0']} L1:{d['L1']} L2:{d['L2']} L3:{d['L3']}  "
                     f"L2+:{d['L2_plus']}/{total} [{bar}] {l2_ratio:.0f}%")

    lines.append("")

    # 二值汇总
    lines.append("  二值维度汇总:")
    lines.append("  " + "-" * 60)
    for dim in ["X1", "X2", "X3", "overall"]:
        r = results[dim]
        bar = "█" * int(r["ratio"] * 20) + "░" * (20 - int(r["ratio"] * 20))
        status = "✅" if r["pass"] else "⚠️"
        lines.append(f"  {dim:8s}  [{bar}]  {r['ratio']:.0%}  → 目标 {r['target']:.0%}  {status}")

    lines.append("")
    lines.append("  深度: L0=不存在 L1=脚本存在 L2=功能完整 L3=集成自动")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = compute_coverage()
    depth_stats = compute_depth_stats()

    if args.json:
        print(json.dumps({
            "generated_at": datetime.now().isoformat(),
            "coverage": results,
            "depth": DEPTH,
            "depth_stats": depth_stats,
            "limitations": {f"{d}[{x}]": n for (d, x), n in LIMITATIONS.items()},
        }, ensure_ascii=False, indent=2))
    else:
        print(format_report(results, depth_stats))

    all_pass = all(r["pass"] for r in results.values())
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
