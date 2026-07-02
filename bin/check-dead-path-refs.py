#!/usr/bin/env python3
"""check-dead-path-refs: 扫 bin/scripts 的 .py 里 .omo/<dir>/ 引用, 校验目录存在 (ISC-9).

治本 ISC-9 (范围收窄): 第8/9次实证修正后, .omo/debt/ 是 omo 合法写面 (mutation-surfaces 声明),
非死引用. 本检测器扫 bin/ + scripts/ 的 .py, 找 .omo/<dir>/ 字面量, 校验目录存在.
只报真死引用 (目录不存在的引用).

用法:
  python bin/check-dead-path-refs.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
OMO = WORKSPACE / ".omo"
REF_RE = re.compile(r"\.mo/([a-zA-Z0-9_-]+)/|\.omo/([a-zA-Z0-9_-]+)")
SCAN_DIRS = ["bin", "scripts"]


def main() -> int:
    dead: list[str] = []
    scanned = 0
    for d in SCAN_DIRS:
        root = WORKSPACE / d
        if not root.is_dir():
            continue
        for f in root.rglob("*.py"):
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
            scanned += 1
            for m in REF_RE.finditer(text):
                subdir = m.group(1) or m.group(2)
                if not subdir:
                    continue
                # 跳过 .omo/PROJECTS/ 引用 — 文件已 deprecated 迁 docs/project-registry.yaml, 治根 F-4 ADR-0122 S1 2026-07-02
                if subdir == "PROJECTS" or subdir.startswith("PROJECTS/"):
                    continue
                if not (OMO / subdir).is_dir():
                    rel = f.relative_to(WORKSPACE)
                    dead.append(f"{rel}: .omo/{subdir}/ (目录不存在)")

    if not dead:
        print(f"✅ dead-path-refs: 0 死引用 (扫描 {scanned} 个 .py, bin/+scripts/ 的 .omo/<dir>/ 引用全存在)")
        return 0
    print(f"❌ dead-path-refs: {len(dead)} 处死引用 (扫描 {scanned} .py):")
    for d in dead[:10]:
        print(f"  - {d}")
    if len(dead) > 10:
        print(f"  ... 及其他 {len(dead) - 10} 处")
    return 1


if __name__ == "__main__":
    sys.exit(main())
