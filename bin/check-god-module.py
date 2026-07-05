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

# 暂豁 debt: 剩余高风险核心 GodModule (F7114ABA Wave 2-3 多会话推进).
# >1500L 但暂豁 --strict error (状态对象化/内联重构/双引擎 DRY, 高风险核心, 仓促拆破坏运行时).
# 见 .omo/_knowledge/audits/f7114aba-gbrain-srp-plan.md + memory [[check-god-module-mechanism]].
# 已达标 3/7 (cycle/serve-http/migrate, PR#109/#110/#111). 剩 4 暂豁, 多会话推进.
EXEMPT_ERRORS = {
    "projects/gbrain/src/core/ai/gateway.ts",       # 2895L: 状态对象化 (71 处引用) + 核心 1610L 提取, P3
    "projects/gbrain/src/commands/doctor.ts",        # 4825L: runDoctor 单函数 2330L inline 重构, P4 极高
    "projects/gbrain/src/core/postgres-engine.ts",   # 4514L: 双引擎 DRY 逐方法对比 SQL (unnest+JOIN), P4
    "projects/gbrain/src/core/pglite-engine.ts",     # 4509L: 双引擎 DRY (同 postgres, 手动 $N), P4
}

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


def scan() -> tuple[list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]]]:
    """扫所有源文件, 返回 (warn_list, error_list, exempt_debt_list), 按行数降序."""
    warn: list[tuple[str, int]] = []
    error: list[tuple[str, int]] = []
    exempt_debt: list[tuple[str, int]] = []  # >1500L 但暂豁 (debt, 见 EXEMPT_ERRORS)
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
            if lines > ERROR_THRESHOLD:
                (exempt_debt if rel in EXEMPT_ERRORS else error).append((rel, lines))
            else:
                warn.append((rel, lines))
    warn.sort(key=lambda x: -x[1])
    error.sort(key=lambda x: -x[1])
    exempt_debt.sort(key=lambda x: -x[1])
    return warn, error, exempt_debt


def print_report(warn: list[tuple[str, int]], error: list[tuple[str, int]], exempt_debt: list[tuple[str, int]] | None = None) -> None:
    exempt_debt = exempt_debt if exempt_debt is not None else []
    total = len(warn) + len(error) + len(exempt_debt)
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
    if exempt_debt:
        print(f"\n🟣 EXEMPT DEBT ({len(exempt_debt)} 文件 > {ERROR_THRESHOLD}L, 暂豁 --strict, 多会话推进):")
        for f, n in exempt_debt:
            print(f"  {n:>5}L  {f}")
        print("   (F7114ABA Wave 2-3 剩余: 状态对象化/runDoctor 重构/双引擎 DRY, 见 SRP plan)")
    if warn:
        print(f"\n🟡 WARN ({len(warn)} 文件 > {WARN_THRESHOLD}L):")
        for f, n in warn:
            print(f"  {n:>5}L  {f}")
    print(f"\n总计: {total} 文件超阈值 (warn {len(warn)} + error {len(error)} + exempt_debt {len(exempt_debt)})")
    print("治法: 用 omo-srp-refactor skill 渐进拆 (纯函数先 → 核心后, 每步 import+test)")


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument(
        "--strict", action="store_true", help=f">{ERROR_THRESHOLD}L 报 error (exit 1)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    warn, error, exempt_debt = scan()

    if args.json:
        print(
            json.dumps(
                {
                    "warn_threshold": WARN_THRESHOLD,
                    "error_threshold": ERROR_THRESHOLD,
                    "warn": [{"file": f, "lines": n} for f, n in warn],
                    "error": [{"file": f, "lines": n} for f, n in error],
                    "exempt_debt": [{"file": f, "lines": n} for f, n in exempt_debt],
                    "total": len(warn) + len(error) + len(exempt_debt),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if (args.strict and error) else 0

    print_report(warn, error, exempt_debt)
    return 1 if (args.strict and error) else 0


if __name__ == "__main__":
    sys.exit(main())
