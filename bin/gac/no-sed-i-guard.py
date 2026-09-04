#!/usr/bin/env python3
"""no-sed-i-guard — sed -i 禁令检测。

检测并阻止使用 sed -i 做添加/删除条目操作。
推荐用 Python read→check→modify→write 模式替代。

Usage:
    python3 bin/gac/no-sed-i-guard.py <file_or_dir> [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def scan_file(path: Path) -> list[dict]:
    """扫描文件中的 sed -i 使用。"""
    violations = []
    try:
        content = path.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(r"sed\s+-i", line):
                violations.append({
                    "file": str(path),
                    "line": i,
                    "content": line.strip(),
                })
    except Exception:
        pass
    return violations


def main():
    parser = argparse.ArgumentParser(description="sed -i 禁令检测")
    parser.add_argument("target", help="文件或目录路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    target = Path(args.target)
    violations = []

    if target.is_file():
        violations = scan_file(target)
    elif target.is_dir():
        for f in target.rglob("*.py"):
            violations.extend(scan_file(f))
        for f in target.rglob("*.sh"):
            violations.extend(scan_file(f))

    result = {
        "violations": len(violations),
        "details": violations,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if violations:
            print(f"❌ Found {len(violations)} sed -i violations:")
            for v in violations:
                print(f"  {v['file']}:{v['line']}: {v['content']}")
        else:
            print("✅ No sed -i violations found")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
