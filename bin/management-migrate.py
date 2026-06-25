#!/usr/bin/env python3
"""P77 R1: management 144 物理迁移 (按 P75 category).

沿 P53 双指针:
1. 创建 3 子目录: workflows/ / playbooks/ / guides/
2. 对每个文件: 在原位加 deprecated + migrated_to 字段
3. 物理 mv 到对应子目录
4. 更新 INDEX.md (如有)

使用:
  python3 bin/management-migrate.py --dry-run  # 仅统计
  python3 bin/management-migrate.py              # 实际迁移
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path


CATEGORY_DIR = {
    "workflows": "workflows",
    "playbooks": "playbooks",
    "guides": "guides",
}


def read_category(path: Path) -> str:
    """读 frontmatter 中的 category 字段."""
    content = path.read_text(encoding="utf-8", errors="ignore")
    if not content.startswith("---\n"):
        return ""
    end = content.find("\n---", 4)
    if end < 0:
        return ""
    fm = content[4:end]
    m = re.search(r"^category:\s*(\S+)", fm, re.MULTILINE)
    return m.group(1) if m else ""


def add_deprecated_and_migrated(content: str, target_path: Path) -> str:
    """加 deprecated + migrated_to 字段 (P53 双指针)."""
    if not content.startswith("---\n"):
        return content
    end = content.find("\n---", 4)
    if end < 0:
        return content
    fm = content[4:end]
    if "migrated_to:" in fm:
        return content  # 已迁移
    new_fm = fm + f"\nmigrated_to: {target_path.name}\ndeprecated-since: 2026-06-23\n"
    return "---\n" + new_fm + content[end:]


def migrate_file(path: Path, dry_run: bool) -> tuple[bool, str]:
    """迁移单个文件. 返回 (migrated, category)."""
    cat = read_category(path)
    if not cat or cat not in CATEGORY_DIR:
        return False, cat
    target_dir = path.parent / CATEGORY_DIR[cat]
    target_path = target_dir / path.name
    if target_path.exists():
        return False, cat  # 已存在, 跳过
    if dry_run:
        return True, cat
    # 物理迁移
    target_dir.mkdir(parents=True, exist_ok=True)
    # P53 双指针: 原位加 deprecated + migrated_to
    content = path.read_text(encoding="utf-8", errors="ignore")
    new_content = add_deprecated_and_migrated(content, target_path)
    path.write_text(new_content, encoding="utf-8")
    # 物理 mv
    shutil.move(str(path), str(target_path))
    return True, cat


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P77: management 144 物理迁移 (按 P75 category)"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--dry-run", action="store_true", help="仅统计")
    parser.add_argument("--category", choices=["workflows", "playbooks", "guides"],
                        help="仅迁移指定 category (默认全部)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    mgr_dir = root / ".omo" / "_knowledge" / "management"
    if not mgr_dir.exists():
        print(f"❌ {mgr_dir} 不存在")
        return 1

    files = sorted(mgr_dir.glob("*.md"))
    # 排除子目录 (避免重复处理)
    files = [f for f in files if f.is_file()]

    stats = Counter()
    migrated = 0
    skipped_no_cat = 0
    skipped_already = 0
    skipped_other = 0

    for f in files:
        if args.category:
            cat = read_category(f)
            if cat != args.category:
                skipped_other += 1
                continue
        ok, cat = migrate_file(f, args.dry_run)
        if ok:
            migrated += 1
            stats[cat] += 1
        elif not cat:
            skipped_no_cat += 1
        elif cat not in CATEGORY_DIR:
            skipped_no_cat += 1
        else:
            skipped_already += 1

    mode = "DRY-RUN" if args.dry_run else "实际迁移"
    print("=" * 60)
    print(f"📁 P77 management 物理迁移 ({mode})")
    print("=" * 60)
    print(f"📁 总文件: {len(files)}")
    print(f"✏️  迁移: {migrated}")
    if stats:
        print()
        print("按 category:")
        for cat, count in sorted(stats.items()):
            print(f"  {cat:<15s} {count:>3d}")
    if skipped_no_cat:
        print(f"⚠️  无 category: {skipped_no_cat}")
    if skipped_already:
        print(f"⏭  已迁移: {skipped_already}")
    if skipped_other:
        print(f"⏭  跳过 (--category filter): {skipped_other}")
    return 0


if __name__ == "__main__":
    sys.exit(main())