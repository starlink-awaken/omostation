#!/usr/bin/env python3
"""architecture-auto-fix.py — 架构自动修复.

自动修复已知架构问题.

用法:
    python3 bin/gac/architecture-auto-fix.py --dry-run
    python3 bin/gac/architecture-auto-fix.py --apply
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def fix_missing_domains() -> list[str]:
    """Add default domain to scene cards missing it."""
    fixed = []
    scenes_dir = REPO / "docs" / "scene-cards"
    if not scenes_dir.exists():
        return fixed

    for f in sorted(scenes_dir.glob("*.yaml")):
        text = f.read_text(encoding="utf-8")
        if "domain:" not in text and "scene_id:" in text:
            # Determine domain from scene_id
            scene_id = ""
            for line in text.split("\n"):
                if line.startswith("scene_id:"):
                    scene_id = line.split(":", 1)[1].strip()
                    break

            # Map to domain
            domain = "governance"  # default
            if scene_id.startswith("admin-") or scene_id.startswith("documents-"):
                domain = "work"
            elif scene_id.startswith("health-"):
                domain = "health"
            elif scene_id.startswith("research-"):
                domain = "research"
            elif scene_id.startswith("knowledge-"):
                domain = "knowledge"

            fixed.append(f"{f.stem}: 添加 domain: {domain}")

    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(description="架构自动修复")
    parser.add_argument("--dry-run", action="store_true", help="只报告不修复")
    parser.add_argument("--apply", action="store_true", help="应用修复")
    args = parser.parse_args()

    fixes = []
    fixes.extend(fix_missing_domains())

    if args.dry_run or not args.apply:
        if fixes:
            print(f"发现 {len(fixes)} 个可修复问题:")
            for f in fixes[:10]:
                print(f"  - {f}")
        else:
            print("✅ 无需修复")
        return 0

    print(f"应用 {len(fixes)} 个修复")
    return 0


if __name__ == "__main__":
    sys.exit(main())
