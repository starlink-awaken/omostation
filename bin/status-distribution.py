#!/usr/bin/env python3
"""P58 R2: frontmatter status 分布趋势报告.

扫描 .omo/_knowledge/ 下所有 .md 文件的 frontmatter, 统计:
- status: active / deprecated / archived / experimental 数量
- lifecycle: ssot / contract / pattern / history 数量
- 各目录的分布差异
- owner 分布

输出: 表格 + 关键洞察
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


def parse_frontmatter(content: str) -> dict[str, str]:
    """简单 frontmatter 解析 (YAML key-value)."""
    if not content.startswith("---\n"):
        return {}
    end = content.find("\n---", 4)
    if end == -1:
        return {}
    fm_text = content[4:end]
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    knowledge = root / ".omo" / "_knowledge"

    if not knowledge.exists():
        print(f"❌ .omo/_knowledge/ not found at {root}")
        return 1

    md_files = list(knowledge.rglob("*.md"))

    status_counter: Counter = Counter()
    lifecycle_counter: Counter = Counter()
    owner_counter: Counter = Counter()
    dir_counter: dict[str, Counter] = {}

    no_fm = 0
    for f in md_files:
        content = f.read_text(encoding="utf-8", errors="ignore")
        fm = parse_frontmatter(content)
        if not fm:
            no_fm += 1
            continue

        status = fm.get("status", "(none)")
        lifecycle = fm.get("lifecycle", "(none)")
        owner = fm.get("owner", "(none)")

        status_counter[status] += 1
        lifecycle_counter[lifecycle] += 1
        owner_counter[owner] += 1

        # 按 top-level dir 分组
        rel = f.relative_to(knowledge)
        top_dir = rel.parts[0] if rel.parts else "(root)"
        if top_dir not in dir_counter:
            dir_counter[top_dir] = Counter()
        dir_counter[top_dir][status] += 1

    print("=" * 70)
    print("📊 P58 R2: frontmatter status 分布报告")
    print("=" * 70)
    print()
    print(f"📁 总文件: {len(md_files)}")
    print(f"📋 有 frontmatter: {len(md_files) - no_fm}")
    print(f"⚠️  缺 frontmatter: {no_fm}")
    print()
    print("─" * 70)
    print("📈 Status 分布 (全局):")
    print("─" * 70)
    total_with_fm = sum(status_counter.values())
    for status, count in sorted(status_counter.items(), key=lambda x: -x[1]):
        pct = 100 * count / total_with_fm if total_with_fm else 0
        bar = "█" * int(pct / 2)
        print(f"  {status:14s} {count:4d}  {pct:5.1f}%  {bar}")
    print()
    print("─" * 70)
    print("📈 Lifecycle 分布 (全局):")
    print("─" * 70)
    for lifecycle, count in sorted(lifecycle_counter.items(), key=lambda x: -x[1]):
        pct = 100 * count / total_with_fm if total_with_fm else 0
        print(f"  {lifecycle:14s} {count:4d}  {pct:5.1f}%")
    print()
    print("─" * 70)
    print("👥 Owner Top-10:")
    print("─" * 70)
    for owner, count in sorted(owner_counter.items(), key=lambda x: -x[1])[:10]:
        print(f"  {owner:30s} {count:4d}")
    print()
    print("─" * 70)
    print("📂 各目录 status 分布 (active 占比排序):")
    print("─" * 70)
    dir_stats = []
    for d, counter in dir_counter.items():
        total = sum(counter.values())
        active = counter.get("active", 0)
        active_pct = 100 * active / total if total else 0
        dir_stats.append((d, total, active, active_pct, counter))
    dir_stats.sort(key=lambda x: -x[3])
    for d, total, active, pct, counter in dir_stats[:20]:
        archived = counter.get("archived", 0)
        deprecated = counter.get("deprecated", 0)
        print(
            f"  {d:40s} total={total:3d}  active={active:3d}({pct:4.1f}%)  "
            f"archived={archived:3d}  deprecated={deprecated:3d}"
        )

    print()
    print("=" * 70)
    print("🔍 关键洞察:")
    print("=" * 70)

    archived = status_counter.get("archived", 0)
    active = status_counter.get("active", 0)
    deprecated = status_counter.get("deprecated", 0)
    history = lifecycle_counter.get("history", 0)
    ssot = lifecycle_counter.get("ssot", 0)
    contract = lifecycle_counter.get("contract", 0)
    pattern = lifecycle_counter.get("pattern", 0)

    # 历史占比
    history_pct = 100 * history / total_with_fm if total_with_fm else 0
    print(f"  • 历史文档占比: {history_pct:.1f}% ({history}/{total_with_fm})")

    # 活跃度
    active_pct = 100 * active / total_with_fm if total_with_fm else 0
    archived_pct = 100 * archived / total_with_fm if total_with_fm else 0
    print(f"  • status active: {active_pct:.1f}% ({active})")
    print(f"  • status archived: {archived_pct:.1f}% ({archived})")
    print(f"  • status deprecated: {100*deprecated/total_with_fm:.1f}% ({deprecated})")

    # SSOT/contract 占比
    critical = ssot + contract + pattern
    critical_pct = 100 * critical / total_with_fm if total_with_fm else 0
    print(f"  • SSOT+Contract+Pattern (权威): {critical_pct:.1f}% ({critical})")

    # 健康度评估
    if active_pct < 30 and archived_pct > 50:
        print(f"  • ✅ 健康: 大量历史归档 + 少量活跃 = 治理成熟态")
    elif active_pct > 50:
        print(f"  • ⚠️  警告: active 占比过高, 可能存在未及时归档")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())