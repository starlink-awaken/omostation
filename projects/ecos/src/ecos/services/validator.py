#!/usr/bin/env python3
"""
eCOS v5 L0 — 协议约束校验器 (ecos-constraint-validator)
===========================================================
委托到真实实现: @学习进化/_knowledge/10-systems/基建架构/ecos-constraint-validator.py
"""
import sys, subprocess
from pathlib import Path

REAL = Path.home() / "Documents" / "@学习进化" / "_knowledge" / "10-systems" / "基建架构" / "ecos-constraint-validator.py"

if __name__ == "__main__":
    if REAL.exists():
        sys.exit(subprocess.call([sys.executable, str(REAL)] + sys.argv[1:]))
    else:
        print(f"❌ 真实校验器不存在: {REAL}")
        sys.exit(1)
