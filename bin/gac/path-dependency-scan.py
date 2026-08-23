#!/usr/bin/env python3
"""Path dependency scanner — detect fragile path calculations before file moves."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import defaultdict

PATTERNS = [
    ("parents[1]", "parents[2]", "parents[3]"),
    ("sys.path.insert", "sys.path.append"),
    ("importlib.util.spec_from_file_location",),
    ("__file__",),
]


def scan_directory(root: Path, extensions: tuple[str, ...]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = defaultdict(list)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue
        if any(part.startswith(".") and part not in (".py",) for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern_group in PATTERNS:
            for pattern in pattern_group:
                if pattern in text:
                    hits[pattern].append(str(path))
                    break
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan for fragile path dependencies")
    ap.add_argument("directory", type=Path, nargs="?", default=Path("tests"))
    ap.add_argument("--extensions", nargs="*", default=[".py", ".sh"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    hits = scan_directory(args.directory, tuple(args.extensions))
    total = sum(len(v) for v in hits.values())

    if args.json:
        import json
        print(json.dumps({"directory": str(args.directory), "total": total, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        print(f"Path dependency scan: {args.directory}")
        print(f"Total files with fragile patterns: {total}")
        for pattern, files in sorted(hits.items()):
            print(f"\n[{pattern}] ({len(files)} files)")
            for f in files[:5]:
                print(f"  {f}")
            if len(files) > 5:
                print(f"  ... and {len(files) - 5} more")

    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
