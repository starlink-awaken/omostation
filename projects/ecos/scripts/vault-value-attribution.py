#!/usr/bin/env python3
"""
eCOS v5 X3 — Vault 价值归因脚本
==================================
Phase X3 / DEBT-X-007 扩展
分析 Vault (学习进化/) 中 Markdown 文件的规模、更新频率与引用密度。

用法:
    python3 vault-value-attribution.py --vault <Documents路径>

输出:
    - 标准模式: 按子目录汇总的文件数/行数/引用数/保鲜状态
    - --json: 结构化输出
"""

import sys
import json
import argparse
import re
from datetime import datetime
from pathlib import Path


SUBDIRS = [
    "驾驶舱",
    "学习进化",
    "工具箱",
    "领域知识库",
    "工作文档",
    "家庭生活",
]

EXCLUDE = {".obsidian", ".git", ".zotero", ".DS_Store", "Zotero", "Claude", "Codex",
           "Manuscripts", "KOS-Inbox", ".antigravitycli", ".UTSystemConfig"}


def analyze_markdown(vault_path: str) -> dict:
    """分析所有 Markdown 文件"""
    vault = Path(vault_path)
    results = {}

    for subdir in SUBDIRS:
        sd = vault / subdir
        if not sd.exists():
            results[subdir] = {"exists": False, "files": 0, "lines": 0, "refs": 0, "max_age": 0}
            continue

        md_files = []
        for f in sd.rglob("*.md"):
            parts = set(f.parts)
            if parts & EXCLUDE:
                continue
            md_files.append(f)

        total_lines = 0
        total_refs = 0
        max_age = 0

        for f in md_files:
            try:
                with open(f, "r") as fh:
                    content = fh.read()
                lines = content.count("\n") + 1
                total_lines += lines

                # 统计内部引用: [[...]] 或 [text](path)
                wiki_links = len(re.findall(r"\[\[([^\]]+)\]\]", content))
                md_links = len(re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content))
                total_refs += wiki_links + md_links

                age = (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
                max_age = max(max_age, age)
            except (OSError, UnicodeDecodeError):
                pass

        results[subdir] = {
            "exists": True,
            "files": len(md_files),
            "lines": total_lines,
            "refs": total_refs,
            "max_age_days": max_age,
            "density": round(total_lines / len(md_files), 1) if md_files else 0,
        }

    return results


def format_report(results: dict) -> str:
    """人类可读报告"""
    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — Vault 价值归因报告 (X3)")
    lines.append("=" * 64)
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    total_files = sum(d["files"] for d in results.values())
    total_lines = sum(d["lines"] for d in results.values())
    total_refs = sum(d["refs"] for d in results.values())

    lines.append(f"  总计: {total_files} 文件 · {total_lines:,} 行 · {total_refs:,} 引用")
    lines.append("")

    lines.append(f"  {'域':12s} {'文件':>5s} {'行数':>7s} {'引用':>5s} {'密度':>5s} {'最旧':>5s}  {'价值'}")
    lines.append("  " + "-" * 58)

    max_files = max((d["files"] for d in results.values()), default=1)
    max_lines = max((d["lines"] for d in results.values()), default=1)
    max_refs = max((d["refs"] for d in results.values()), default=1)

    for subdir in SUBDIRS:
        d = results.get(subdir, {"exists": False})
        if not d.get("exists"):
            lines.append(f"  {subdir:12s}  {'—':>5s}  {'—':>7s}  {'—':>5s}  {'—':>5s}  {'—':>5s}")
            continue

        # 价值得分: 规模 40% + 引用密度 30% + 新鲜度 30%
        scale_score = (d["files"] / max_files) * 40
        ref_score = (d["refs"] / max_refs) * 30 if max_refs > 0 else 0
        fresh_score = max(0, (60 - d["max_age_days"]) / 60) * 30
        value = scale_score + ref_score + fresh_score

        age_str = f"{d['max_age_days']}d" if d["max_age_days"] > 0 else "0d"
        bar = "█" * int(value / 10) + "░" * (10 - int(value / 10))

        lines.append(
            f"  {subdir:12s} {d['files']:5d} {d['lines']:6,} {d['refs']:5d} "
            f"{d['density']:4.0f}  {age_str:>5s}  {value:4.0f} {bar}"
        )

    lines.append("")
    lines.append("  价值公式: 规模 40% + 引用密度 30% + 新鲜度 30%")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 Vault 价值归因")
    parser.add_argument("--vault", required=True, help="Documents vault 路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not Path(args.vault).exists():
        print(f"❌ Vault 不存在: {args.vault}", file=sys.stderr)
        sys.exit(2)

    results = analyze_markdown(args.vault)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_report(results))


if __name__ == "__main__":
    main()
