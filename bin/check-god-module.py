#!/usr/bin/env python3
"""God Module 检测 — 单文件 >800L warn, >1500L error.

防 God Module 增长 (TASK-F7114ABA deliverable: >800L lint gate).
原型 A5 (Growth & Underinvestment): 快速推进 + SRP 纪律缺失 → 单文件膨胀.
此脚本把"文件大小"变成可追踪数字, 防新 God Module 产生 + 暴露历史债.

扫 projects/**/*.py + **/*.ts (跳过 node_modules/.venv/_legacy/test fixtures).
默认报告型 (exit 0); --strict 模式 >1500L 报 error (exit 1, 可挂 pre-commit/CI).

用法:
  python3 bin/check-god-module.py           # 报告 (exit 0)
  python3 bin/check-god-module.py --strict  # gate (有 >1500L 则 exit 1)
  python3 bin/check-god-module.py --json    # JSON 输出 (供 dashboard)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# CI 可移植: __file__ 定位 workspace
WORKSPACE = Path(__file__).resolve().parents[1]

WARN_THRESHOLD = 800  # warn: 单文件超此报黄
ERROR_THRESHOLD = 1500  # error: 单文件超此报红 (--strict 时 exit 1)

# 扫描范围 + 排除 (避免噪音: 生成代码/测试快照/旧码)
SCAN_GLOBS = ("projects/**/*.py", "projects/**/*.ts")
EXCLUDE_MARKERS = (
    "node_modules",
    ".venv",
    "_legacy",
    "/dist/",
    "/build/",
    ".pb.py",
    "/tests/",
    "/test/",
    ".test.",  # 测试文件长是正常的 (用例多), 不是 God Module 架构问题
)


def _count_lines(path: Path) -> int:
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _is_excluded(path: Path) -> bool:
    s = str(path)
    return any(marker in s for marker in EXCLUDE_MARKERS)


def scan() -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """扫所有源文件, 返回 (warn_list, error_list), 按行数降序."""
    warn: list[tuple[str, int]] = []
    error: list[tuple[str, int]] = []
    seen: set[Path] = set()
    for pattern in SCAN_GLOBS:
        for f in WORKSPACE.glob(pattern):
            if f in seen or not f.is_file() or _is_excluded(f):
                continue
            seen.add(f)
            lines = _count_lines(f)
            if lines <= WARN_THRESHOLD:
                continue
            rel = str(f.relative_to(WORKSPACE))
            (error if lines > ERROR_THRESHOLD else warn).append((rel, lines))
    warn.sort(key=lambda x: -x[1])
    error.sort(key=lambda x: -x[1])
    return warn, error


def print_report(warn: list[tuple[str, int]], error: list[tuple[str, int]]) -> None:
    total = len(warn) + len(error)
    print("=" * 60)
    print(f"📦 God Module 检测 (>{WARN_THRESHOLD}L warn, >{ERROR_THRESHOLD}L error)")
    print("=" * 60)
    if not total:
        print("✅ 无 >800L 单文件 (SRP 健康)")
        return
    if error:
        print(f"\n🔴 ERROR ({len(error)} 文件 > {ERROR_THRESHOLD}L, --strict 时阻塞):")
        for f, n in error:
            print(f"  {n:>5}L  {f}")
    if warn:
        print(f"\n🟡 WARN ({len(warn)} 文件 > {WARN_THRESHOLD}L):")
        for f, n in warn:
            print(f"  {n:>5}L  {f}")
    print(f"\n总计: {total} 文件超阈值 (warn {len(warn)} + error {len(error)})")
    print("治法: 用 omo-srp-refactor skill 渐进拆 (纯函数先 → 核心后, 每步 import+test)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--strict", action="store_true", help=f">{ERROR_THRESHOLD}L 报 error (exit 1)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    warn, error = scan()

    if args.json:
        print(
            json.dumps(
                {
                    "warn_threshold": WARN_THRESHOLD,
                    "error_threshold": ERROR_THRESHOLD,
                    "warn": [{"file": f, "lines": n} for f, n in warn],
                    "error": [{"file": f, "lines": n} for f, n in error],
                    "total": len(warn) + len(error),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if (args.strict and error) else 0

    print_report(warn, error)
    return 1 if (args.strict and error) else 0


if __name__ == "__main__":
    sys.exit(main())
