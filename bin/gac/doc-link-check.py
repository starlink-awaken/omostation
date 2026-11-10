#!/usr/bin/env python3
"""
doc-link-check.py — Check markdown documentation links for validity.

Usage:
  uv run python3 bin/gac/doc-link-check.py
  uv run python3 bin/gac/doc-link-check.py --json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

def _is_gitignored(path: Path) -> bool:
    """`path` 是否被 .gitignore 覆盖 (运行期生成物, 干净检出里没有)。

    与 `check-cross-refs` / `CR-OMO-SURFACE-01` 同一类盲点: 判据只看文件系统
    就会「干净检出不报、本机报」。探测失败一律返回 False (不豁免), 保持偏严。
    """
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel.as_posix()],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
    except Exception:  # noqa: BLE001
        return False
    return proc.returncode == 0


MD_DIRS = [
    REPO_ROOT / "docs",
    REPO_ROOT / ".omo",
    REPO_ROOT / "projects",
]


def check_links(dir_path: Path) -> list:
    broken = []
    if not dir_path.exists():
        return broken

    for f in dir_path.rglob("*.md"):
        if ".git" in str(f):
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue

        for m in re.finditer(r"\[.*?\]\((.*?)\)", text):
            target = m.group(1)
            if target.startswith("http://") or target.startswith("https://"):
                continue
            if target.startswith("/"):
                target_path = Path(target)
                if not target_path.exists():
                    if _is_gitignored(target_path):
                        continue
                    broken.append({
                        "file": str(f.relative_to(REPO_ROOT)),
                        "link": target,
                        "issue": "absolute path does not exist",
                    })
            elif target.startswith(".") or target.startswith(".."):
                target_path = (f.parent / target).resolve()
                if not target_path.exists():
                    if _is_gitignored(target_path):
                        continue
                    broken.append({
                        "file": str(f.relative_to(REPO_ROOT)),
                        "link": target,
                        "issue": "relative path does not exist",
                    })
            else:
                target_path = (f.parent / target).resolve()
                if not target_path.exists():
                    if _is_gitignored(target_path):
                        continue
                    broken.append({
                        "file": str(f.relative_to(REPO_ROOT)),
                        "link": target,
                        "issue": "path does not exist",
                    })

    return broken


def main() -> None:
    parser = argparse.ArgumentParser(description="Documentation link checker")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    all_broken = []
    for d in MD_DIRS:
        all_broken.extend(check_links(d))

    if args.json:
        result = {
            "check": "doc_link_validity",
            "broken_count": len(all_broken),
            "broken_links": all_broken[:50],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if not all_broken else 1)

    print("Documentation Link Check")
    print("=" * 50)
    if all_broken:
        print(f"FAIL: {len(all_broken)} broken links found")
        for b in all_broken[:20]:
            print(f"  - {b['file']}: {b['link']} ({b['issue']})")
        sys.exit(1)
    else:
        print("PASS: All documentation links valid")
        sys.exit(0)


if __name__ == "__main__":
    main()
