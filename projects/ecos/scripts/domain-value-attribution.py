#!/usr/bin/env python3
"""
eCOS v5 X3 — 域系统价值归因脚本
==================================
Phase X3 / DEBT-X-007 最终扩展
分析工作文档和家庭生活两个域的文档规模、活跃度与价值贡献。

用法:
    python3 domain-value-attribution.py --vault <Documents路径>

输出:
    - 标准模式: 按子目录汇总的文件数/行数/活跃度/价值分
    - --json: 结构化输出
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path


DOMAINS = {
    "工作文档": {
        "subdirs": ["卫健委", "国转中心", "合同协议", "个人资料", "公文模版", "法律法规", "临时文件"],
        "value_tier": 3,
        "label": "业务价值",
    },
    "家庭生活": {
        "subdirs": ["00.管理系统", "01.成员档案", "02.医疗健康", "03.育儿成长", "04.家庭日常", "05.资产设备", "99.文件中转"],
        "value_tier": 3,
        "label": "业务价值",
    },
}

EXCLUDE = {".obsidian", ".git", ".DS_Store", "CLAUDE.md", "STATE.md", "Plans"}


def analyze_subdir(root: Path, subdirs: list[str]) -> list[dict]:
    """分析子目录"""
    results = []
    for sd_name in subdirs:
        sd = root / sd_name
        if not sd.exists():
            results.append({"name": sd_name, "exists": False, "files": 0, "lines": 0, "max_age": 0})
            continue

        md_files = []
        for f in sd.rglob("*.md"):
            parts = set(f.parts)
            if parts & EXCLUDE:
                continue
            md_files.append(f)

        total_lines = 0
        max_age = 0
        for f in md_files:
            try:
                with open(f, "r") as fh:
                    total_lines += sum(1 for _ in fh)
                age = (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
                max_age = max(max_age, age)
            except (OSError, UnicodeDecodeError):
                pass

        results.append({
            "name": sd_name,
            "exists": True,
            "files": len(md_files),
            "lines": total_lines,
            "max_age_days": max_age,
            "density": round(total_lines / len(md_files), 1) if md_files else 0,
        })

    return results


def format_report(all_results: dict) -> str:
    """人类可读报告"""
    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — 域系统价值归因报告 (X3)")
    lines.append("=" * 64)
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    grand_files = 0
    grand_lines = 0

    for domain_name, info in DOMAINS.items():
        results = all_results[domain_name]
        total_f = sum(r["files"] for r in results)
        total_l = sum(r["lines"] for r in results)
        grand_files += total_f
        grand_lines += total_l

        lines.append(f"  ── {domain_name} (value_tier={info['value_tier']}, {info['label']}) ──")
        lines.append(f"  总文件: {total_f}  总行数: {total_l:,}")
        lines.append(f"  {'子域':20s} {'文件':>5s} {'行数':>7s} {'密度':>5s} {'最旧':>5s}  {'活跃度'}")
        lines.append("  " + "-" * 54)

        max_f = max((r["files"] for r in results), default=1)
        max_l = max((r["lines"] for r in results), default=1)

        for r in results:
            if not r["exists"]:
                lines.append(f"  {r['name']:20s}  {'—':>5s}  {'—':>7s}  {'—':>5s}  {'—':>5s}")
                continue

            # 活跃度得分: 规模 40% + 新鲜度 60%
            scale = (r["files"] / max_f) * 40 if max_f > 0 else 0
            fresh = max(0, (365 - r["max_age_days"]) / 365) * 60  # 以年为单位
            activity = scale + fresh

            age_str = f"{r['max_age_days']}d" if r["max_age_days"] > 0 else "0d"
            bar = "█" * int(activity / 10) + "░" * (10 - int(activity / 10))

            lines.append(
                f"  {r['name']:20s} {r['files']:5d} {r['lines']:6,} "
                f"{r['density']:4.0f}  {age_str:>5s}  {activity:4.0f} {bar}"
            )

        # 域价值得分
        avg_activity = sum(
            (r["files"] / max_f) * 40 + max(0, (365 - r["max_age_days"]) / 365) * 60
            for r in results if r["exists"] and r["files"] > 0
        ) / max(1, sum(1 for r in results if r["exists"] and r["files"] > 0))

        lines.append(f"  → 域活跃度均值: {avg_activity:.0f}/100")
        lines.append("")

    lines.append(f"  跨域总计: {grand_files} 文件 · {grand_lines:,} 行")
    lines.append("  活跃度公式: 规模 40% + 新鲜度(1年内) 60%")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 域系统价值归因")
    parser.add_argument("--vault", required=True, help="Documents vault 路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault)
    if not vault.exists():
        print(f"❌ Vault 不存在: {vault}", file=sys.stderr)
        sys.exit(2)

    all_results = {}
    for domain_name, info in DOMAINS.items():
        root = vault / domain_name
        if root.exists():
            all_results[domain_name] = analyze_subdir(root, info["subdirs"])
        else:
            all_results[domain_name] = []

    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2, default=str))
    else:
        print(format_report(all_results))


if __name__ == "__main__":
    main()
