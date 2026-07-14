#!/usr/bin/env python3
"""P96 R2: venv 依赖一致性检查工具.

检测 kairon venv 关键依赖是否完整, 缺则自动 install.
修复 P95 R3 暴露的 pyyaml fragile 问题.

使用:
  python3 bin/ssot/venv-yaml-check.py              # 检查 + 自动 install
  python3 bin/ssot/venv-yaml-check.py --check     # 仅检查, 不 install
  python3 bin/ssot/venv-yaml-check.py --list      # 列出所有需检查的依赖
"""

from __future__ import annotations

import argparse
import subprocess
import sys

# 关键依赖清单 (governance tools 必需)
REQUIRED = {
    "pyyaml": "yaml",
}


def check_import(name: str) -> bool:
    """检查 import 是否成功."""
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="P96: venv 依赖一致性检查")
    parser.add_argument("--check", action="store_true", help="仅检查, 不 install")
    parser.add_argument("--list", action="store_true", help="列出所有依赖")
    parser.add_argument("--venv", default="projects/kairon",
                        help="venv 目录 (用于 uv pip install)")
    args = parser.parse_args()

    if args.list:
        print("📋 关键依赖清单 (governance tools 必需):")
        for pkg, mod in REQUIRED.items():
            status = "✅" if check_import(mod) else "❌"
            print(f"   {status} {pkg}  (import {mod})")
        return 0

    missing = [pkg for pkg, mod in REQUIRED.items() if not check_import(mod)]

    if not missing:
        print("✅ 所有关键依赖完整")
        return 0

    print(f"❌ 缺失依赖: {missing}")

    if args.check:
        return 1

    # 自动 install
    print(f"🔧 自动 install 到 {args.venv} ...")
    r = subprocess.run(
        ["uv", "pip", "install", *missing, "--directory", args.venv],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        print(f"❌ install 失败: {r.stderr[:300]}")
        return 1

    # 验证
    for pkg, mod in REQUIRED.items():
        if check_import(mod):
            print(f"   ✅ {pkg}  OK")
        else:
            print(f"   ❌ {pkg}  STILL MISSING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
