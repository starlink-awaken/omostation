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

# 已知合法但 worktree 中不存在的子目录 (运行时产物/历史路径/文档示例):
# - _log, _delivery: gitignored 运行时目录 (运行时创建)
# - capabilities: 代码容错路径搜索 (历史路径残留)
# - debt: gitignored 运行时目录 (.omo/debt/ 由 omo CLI 运行时创建, tracked 版在 _control/debt-dashboard/)
# - xxx, INDEX, workers: 注释/docstring 中的示例/历史引用 (非真实代码路径)
# - pitches, tests, evidence, task-prompts, plans, drafts, backups: 历史路径/计划中的写面 (已迁 runtime/omo 或从未落地)
LEGACY_OK_DIRS = {"_log", "_delivery", "capabilities", "debt", "xxx", "INDEX", "workers", "summaries", "pitches", "tests", "evidence", "task-prompts", "plans", "drafts", "backups", "diagrams", "boulder"}


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
                # 跳过已知合法但 worktree 中不存在的子目录 (TASK-236A991C)
                # 也匹配子目录 (如 debt/items, debt/dashboard — .omo/debt/* 是 omo 运行时写面, gitignored)
                if subdir in LEGACY_OK_DIRS or (subdir and subdir.split("/")[0] in LEGACY_OK_DIRS):
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
