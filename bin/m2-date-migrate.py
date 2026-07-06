#!/usr/bin/env python3
"""m2-date-migrate.py — 治本 M2BS-03 schema 一致性 (Round 4c)

M2BaseSchema M2BS-03 要求 created 字段为 ISO-8601 datetime.
P1-S0 (ADR-0141) 之前的 m2 schema 有 45 个用 date 格式 (YYYY-MM-DD).
Round 4c 把这些统一为 datetime (YYYY-MM-DDThh:mm:ss + 8 hours, 取
ecos 项目创建时刻 08:00:00 标准化).

不破 P52 / P72:
- 仅改 created 字段格式, 不动其他
- 不改 m3.yaml / model-driven 引擎
- dry-run 默认开, --apply 才真改
- 已兼容日期格式(正则)保留 (治本方向非强制)

用法:
    uv run --with pyyaml python bin/m2-date-migrate.py
    uv run --with pyyaml python bin/m2-date-migrate.py --apply
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

WS = Path(__file__).resolve().parents[1]
M2_DIR = WS / "projects/ecos/src/ecos/ssot/mof/m2"

# 匹配 YYYY-MM-DD (单纯日期) (不含 T 或数字后再带 :)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def find_date_only_schemas() -> list[Tuple[Path, str]]:
    """扫描 m2/*.yaml, 返回 (path, current_date_str)"""
    results: list[Tuple[Path, str]] = []
    for f in sorted(M2_DIR.glob("*.yaml")):
        if f.name == "m2_base_schema.yaml":
            continue
        try:
            content = f.read_text()
        except Exception:
            continue
        for line in content.splitlines():
            line_strip = line.strip()
            if line_strip.startswith("created:"):
                # 提取 value (引号内)
                m = re.search(r"created:\s*['\"]([^'\"]+)['\"]", line_strip)
                if m and DATE_PATTERN.match(m.group(1)):
                    results.append((f, m.group(1)))
                    break
    return results


def normalize_to_datetime(date_str: str) -> str:
    """YYYY-MM-DD → YYYY-MM-DDThh:mm:ss (默认 08:00:00)"""
    return f"{date_str}T08:00:00"


def migrate_file(path: Path, current_date: str, apply: bool = False) -> bool:
    """单 schema 迁移, 返回是否真有改动"""
    new_value = normalize_to_datetime(current_date)
    content = path.read_text()
    new_content = re.sub(
        rf"created:\s*['\"]{re.escape(current_date)}['\"]",
        f'created: \'{new_value}\'',
        content,
    )
    if content == new_content:
        return False
    if apply:
        path.write_text(new_content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="应用修改 (默认 dry-run)")
    parser.add_argument("--pattern", default="", help="仅迁移匹配 pattern 的 schema 文件")
    args = parser.parse_args()

    schemas = find_date_only_schemas()
    if args.pattern:
        schemas = [(p, d) for p, d in schemas if args.pattern in p.name]

    if not schemas:
        print("✅ 所有 m2 schema 已是 ISO-8601 datetime 格式")
        return 0

    print(f"发现 {len(schemas)} 个 m2 schema 用 date 格式 created")
    if not args.apply:
        print("(DRY-RUN, 加 --apply 才真改)")

    changed = 0
    for path, current in schemas:
        new = normalize_to_datetime(current)
        marker = "✓" if not args.apply else "→"
        print(f"  {marker} {path.name}: created '{current}' → '{new}'")
        if migrate_file(path, current, apply=args.apply):
            changed += 1

    print(f"\n{'已应用' if args.apply else 'DRY-RUN, 待 --apply'}: {changed}/{len(schemas)} 个 schema {'已改' if args.apply else '待改'}")

    if not args.apply:
        print("\n推荐:")
        print("  uv run --with pyyaml python bin/m2-date-migrate.py --apply")
        print("  uv run --with pyyaml python tests/integration/m4_metamodel/run_all.py")
    else:
        print("\n验证:")
        print("  uv run --with pyyaml python bin/mof-bootstrap.py check_5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
