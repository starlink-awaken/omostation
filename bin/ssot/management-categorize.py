#!/usr/bin/env python3
"""P75 R1: management 142 拆分 (frontmatter 分类).

沿用 P53 双指针原则, 不物理迁移 142 个文件, 而是为每个文件加 `category` 字段
让未来筛选/重组变得简单. 类别基于文件名+note 自动判断.

类目:
  - workflows/   流程类 (含 audit / closeout / hardening / playbook / migration / optimization)
  - playbooks/  操作类 (含 append-only-log / schemas / ssot)
  - guides/     概念类 (含 architecture / explainer / analysis)

使用:
  python3 bin/ssot/management-categorize.py          # 加 category 字段
  python3 bin/ssot/management-categorize.py --stats # 仅统计
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


CATEGORY_RULES = {
    "workflows": [
        "audit", "closeout", "hardening", "triage",
        "migration", "playbook", "optimization",
        "bet-", "review", "report", "final-state",
        "phase", "snapshot", "blueprint", "complete-plan",
    ],
    "playbooks": [
        "append-only-log", "schemas", "ssot", "manifest",
        "defensive", "replay", "node", "mvp",
    ],
    "guides": [
        "architecture", "explainer", "analysis",
        "deep", "layer", "modeling", "intro",
    ],
}


def detect_category(filename: str) -> str:
    """基于文件名检测类目."""
    f = filename.lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(kw in f for kw in keywords):
            return category
    return "workflows"  # 默认


def add_category(path: Path, dry_run: bool = False) -> tuple[bool, str]:
    """为 .md 文件加 category 字段. 返回 (changed, category)."""
    content = path.read_text(encoding="utf-8", errors="ignore")
    if not content.startswith("---\n"):
        return False, ""
    end = content.find("\n---", 4)
    if end < 0:
        return False, ""

    fm = content[4:end]
    # 已有 category 字段
    if re.search(r"^category:", fm, re.MULTILINE):
        return False, ""

    cat = detect_category(path.name)
    new_fm = f"category: {cat}\n" + fm
    new_content = "---\n" + new_fm + content[end:]

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return True, cat


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P75: management/ 142 拆分 (frontmatter 分类)"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--stats", action="store_true", help="仅统计")
    parser.add_argument("--dry-run", action="store_true", help="dry-run, 不写")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    mgr_dir = root / ".omo" / "_knowledge" / "management"
    if not mgr_dir.exists():
        print(f"❌ {mgr_dir} 不存在")
        return 1

    files = sorted(mgr_dir.glob("*.md"))
    total = len(files)
    stats = Counter()
    modified = 0

    for f in files:
        if args.stats:
            # 仅看现有 frontmatter 中的 category (无则默认)
            content = f.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^category:\s*(\S+)", content, re.MULTILINE)
            cat = m.group(1) if m else "(unclassified)"
            stats[cat] += 1
        else:
            changed, cat = add_category(f, args.dry_run)
            stats[cat] += 1
            if changed:
                modified += 1

    print("=" * 60)
    print("📊 P75 management/ 142 分类统计")
    print("=" * 60)
    print(f"📁 总文件: {total}")
    if not args.stats:
        mode = "dry-run" if args.dry_run else "实际修改"
        print(f"✏️  {mode}: {modified}")
    print()
    print("按类目:")
    for cat, count in stats.most_common():
        print(f"  {cat:<15s} {count:>3d}")
    print()
    if not args.stats:
        print("✅ 完成, 未来可基于 category 字段筛选/重组")
    else:
        print("📌 统计完成, 加 --dry-run 实际修改")
    return 0


if __name__ == "__main__":
    sys.exit(main())