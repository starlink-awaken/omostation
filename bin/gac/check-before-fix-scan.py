#!/usr/bin/env python3
"""check-before-fix-scan — Check-before-fix 协议扫描。

检测脚本是否先读 DEFAULT_* 路径常量再修改文件。

Usage:
    python3 bin/gac/check-before-fix-scan.py <script_path> [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def scan_script(path: Path) -> dict:
    """扫描脚本是否遵循 check-before-fix 协议。"""
    content = path.read_text(encoding="utf-8")

    # 检查是否有 DEFAULT_ 常量引用
    has_default_ref = bool(re.search(r"DEFAULT_\w+", content))
    # 检查是否有 read→check→modify→write 模式
    has_read_check = "read_text" in content and ("check" in content or "validate" in content)
    # 检查是否有 sed -i (禁止)
    has_sed_i = bool(re.search(r"sed\s+-i", content))

    return {
        "file": str(path),
        "has_default_reference": has_default_ref,
        "has_read_check_pattern": has_read_check,
        "has_sed_i_violation": has_sed_i,
        "compliant": has_default_ref and has_read_check and not has_sed_i,
    }


def main():
    parser = argparse.ArgumentParser(description="Check-before-fix 协议扫描")
    parser.add_argument("script", help="脚本路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.script)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    result = scan_script(path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        icon = "✅" if result["compliant"] else "❌"
        print(f"{icon} {path.name}: {'COMPLIANT' if result['compliant'] else 'VIOLATION'}")
        if result["has_sed_i_violation"]:
            print("  ❌ Uses sed -i (forbidden)")

    return 0 if result["compliant"] else 1


if __name__ == "__main__":
    sys.exit(main())
