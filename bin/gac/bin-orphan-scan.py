#!/usr/bin/env python3
"""BET-Y1Q2-T6-03: Find zero-reference scripts in bin/ for archival.

Scans bin/ for .py and .sh scripts, checks references in Makefile, hooks,
CI workflows, AGENTS.md, and cross-script imports. Reports orphans.

Usage:
  python3 bin/gac/bin-orphan-scan.py
  python3 bin/gac/bin-orphan-scan.py --json
  python3 bin/gac/bin-orphan-scan.py --archive  # move to bin/_archive/
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / "bin"
ARCHIVE_DIR = BIN_DIR / "_archive"

SKIP_PATTERNS = {"_lib.py", "__init__.py", "_archive", "_orphan_scan.py"}
REF_DIRS = [
    ROOT / "Makefile",
    ROOT / ".githooks",
    ROOT / ".github" / "workflows",
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "README.md",
]


def _is_lib_or_test(name: str) -> bool:
    if name.endswith("_lib.py") or name.startswith("test_") or name == "__init__.py":
        return True
    return False


def _collect_scripts() -> list[Path]:
    scripts = []
    for ext in ("*.py", "*.sh"):
        for p in BIN_DIR.rglob(ext):
            if any(skip in str(p) for skip in SKIP_PATTERNS):
                continue
            if _is_lib_or_test(p.name):
                continue
            scripts.append(p)
    return sorted(scripts)


def _count_references(script: Path, all_scripts: list[Path]) -> int:
    name = script.name
    stem = script.stem
    refs = 0
    ref_text = ""

    for path in REF_DIRS:
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if name in text or stem in text:
                    refs += 1
            except Exception:
                pass
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file() and f.suffix in (".yml", ".yaml", ".sh", ".md", ".py"):
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        if name in text or stem in text:
                            refs += 1
                    except Exception:
                        pass

    for other in all_scripts:
        if other == script:
            continue
        try:
            text = other.read_text(encoding="utf-8", errors="ignore")
            if name in text or stem in text:
                refs += 1
        except Exception:
            pass

    return refs


def scan_orphans() -> list[dict]:
    scripts = _collect_scripts()
    orphans = []
    for s in scripts:
        ref_count = _count_references(s, scripts)
        if ref_count == 0:
            orphans.append({
                "path": str(s.relative_to(ROOT)),
                "name": s.name,
                "refs": ref_count,
                "size_bytes": s.stat().st_size,
            })
    return sorted(orphans, key=lambda x: x["path"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--archive", action="store_true", help="move orphans to bin/_archive/")
    parser.add_argument("--threshold", type=int, default=0, help="max ref count to include (default: 0)")
    args = parser.parse_args()

    orphans = scan_orphans()
    if args.threshold > 0:
        scripts = _collect_scripts()
        orphans = []
        for s in scripts:
            ref_count = _count_references(s, scripts)
            if ref_count <= args.threshold:
                orphans.append({
                    "path": str(s.relative_to(ROOT)),
                    "name": s.name,
                    "refs": ref_count,
                    "size_bytes": s.stat().st_size,
                })
        orphans.sort(key=lambda x: x["path"])

    if args.json:
        print(json.dumps({"total_scripts": len(_collect_scripts()), "orphans": len(orphans), "items": orphans}, indent=2, ensure_ascii=False))
        return 0

    total = len(_collect_scripts())
    print(f"bin/ scripts: {total}")
    print(f"Zero-reference orphans: {len(orphans)}")
    print()
    for o in orphans:
        print(f"  {o['path']}  ({o['size_bytes']} bytes)")

    if args.archive and orphans:
        ARCHIVE_DIR.mkdir(exist_ok=True)
        archived = 0
        for o in orphans:
            src = ROOT / o["path"]
            dst = ARCHIVE_DIR / src.name
            if dst.exists():
                continue
            shutil.move(str(src), str(dst))
            archived += 1
            print(f"  → archived: {o['path']}")
        print(f"\nArchived {archived} scripts to {ARCHIVE_DIR.relative_to(ROOT)}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
