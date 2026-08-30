#!/usr/bin/env python3
"""
adr-link-validator.py — Validate ADR file path references.

Usage:
  uv run python3 bin/gac/adr-link-validator.py
  uv run python3 bin/gac/adr-link-validator.py --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ADR_DIRS = [
    REPO_ROOT / ".omo" / "_knowledge" / "decisions",
    REPO_ROOT / "docs" / "adr",
]


def find_broken_links(adr_dir: Path) -> list:
    broken = []
    if not adr_dir.exists():
        return broken

    for f in adr_dir.glob("*.md"):
        text = f.read_text(errors="ignore")
        for m in re.finditer(r"\[.*?\]\((.*?)\)", text):
            target = m.group(1)
            if target.startswith("/"):
                target_path = Path(target)
                if not target_path.exists() and not target.startswith("http"):
                    broken.append({
                        "adr": str(f.relative_to(REPO_ROOT)),
                        "link": target,
                        "issue": "target does not exist",
                    })
            elif target.startswith(".") or target.startswith(".."):
                # Repo-root relative fallback: many ADRs link to repo-root
                # entries like `.agents/skills/...` or `docs/...` instead of
                # nesting the path under the ADR file's own directory.
                # Try REPO_ROOT first, then fall back to ADR-local resolution.
                target_path = (REPO_ROOT / target).resolve()
                if not target_path.exists():
                    target_path = (f.parent / target).resolve()
                if not target_path.exists() and not target.startswith("http"):
                    broken.append({
                        "adr": str(f.relative_to(REPO_ROOT)),
                        "link": target,
                        "issue": "target does not exist",
                    })
    return broken


def main() -> None:
    parser = argparse.ArgumentParser(description="ADR link validator")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    all_broken = []
    for adr_dir in ADR_DIRS:
        all_broken.extend(find_broken_links(adr_dir))

    if args.json:
        result = {
            "check": "adr_link_validity",
            "total_checked": sum(len(list(d.glob("*.md"))) for d in ADR_DIRS if d.exists()),
            "broken_count": len(all_broken),
            "broken_links": all_broken[:50],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if not all_broken else 1)

    print("ADR Link Validity Check")
    print("=" * 50)
    if all_broken:
        print(f"FAIL: {len(all_broken)} broken links found")
        for b in all_broken[:20]:
            print(f"  - {b['adr']}: {b['link']} ({b['issue']})")
        sys.exit(1)
    else:
        total = sum(len(list(d.glob("*.md"))) for d in ADR_DIRS if d.exists())
        print(f"PASS: All {total} ADR links valid")
        sys.exit(0)


if __name__ == "__main__":
    main()
