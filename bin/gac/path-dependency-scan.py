#!/usr/bin/env python3
"""路径依赖扫描器 — 检测 bin/ 脚本中对特定路径的硬编码依赖。

用法:
  python3 bin/gac/path-dependency-scan.py [--path <parent>] [--json]

SSOT: .omo/_knowledge/patterns/p87-systemic-optimization-retro.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
BIN_DIR = WORKSPACE / "bin"


def scan(parent: str = "bin") -> list[dict]:
    hits: list[dict] = []
    for py in BIN_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        if 'parents[1]' in text or f'"{parent}"' in text or f"'{parent}'" in text:
            hits.append(
                {
                    "file": str(py.relative_to(WORKSPACE)),
                    "matches": text.count('parents[1]'),
                }
            )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="bin", help="Parent path to scan for")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    hits = scan(args.path)
    if args.json:
        print(json.dumps({"parent": args.path, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        if not hits:
            print(f"✅ 未发现对 `{args.path}` 的硬编码路径依赖")
            return 0
        print(f"🔴 发现 {len(hits)} 个文件硬编码依赖 `{args.path}`:")
        for h in hits[:20]:
            print(f"  {h['file']} ({h['matches']} 处)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
