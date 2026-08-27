#!/usr/bin/env python3
"""Per-package mypy error report + regression gate (服务 DEBT-CI-MYPY-STRICT).

真相调法: cd pkg && MYPYPATH=src mypy src (--namespace-packages --explicit-package-bases --exclude tests/).
旧调法 `mypy src` 无 MYPYPATH 对多数包给假绿 (mypy 解析不出跨包 import 当 Any 静默通过),
仅 minerva/sophia 撞模块映射冲突才报错 — 故旧 typecheck 虚标 "16/16 strict" 实为假象.
真实存量 1245 errors (9 包有错 / 7 包干净), 见 mypy-baseline.yaml.

两模式:
  report (默认): 打印每包错误数 + top N (真相诊断)
  gate (--baseline file.yaml): regression gate — 任一包超 baseline 退出 1
        (DRY 复用 .omo/_truth/registry/direct-io-baseline.yaml 的 baseline-suppression 范式)
  update (--baseline file.yaml --update): 刷新 baseline (修了真错误后降数)

Usage:
    python scripts/mypy_report.py                                 # 报表
    python scripts/mypy_report.py --top 5                         # top 5
    python scripts/mypy_report.py --json                          # JSON
    python scripts/mypy_report.py --baseline mypy-baseline.yaml   # regression gate
    python scripts/mypy_report.py --baseline mypy-baseline.yaml --update   # 刷新 baseline
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

# 锚定 kairon 根 (scripts/ 的父目录), 不硬编码绝对路径 — CI 可移植
KAIRON_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = KAIRON_ROOT / "packages"

# 与 Makefile typecheck 对齐的 mypy 标志
_MYPY_FLAGS = [
    "--namespace-packages",
    "--explicit-package-bases",
    "--exclude",
    "tests/",
    "--no-incremental",
]


def count_mypy_errors(pkg_dir: Path) -> int:
    """真相调法跑 mypy 数某包错误: cd pkg && MYPYPATH=src mypy src.

    MYPYPATH=src 让 mypy 正确解析本包模块 (消 src.x vs x 冲突), 才能真检查跨包 import.
    否则 mypy 解析不出当 Any 处理 → 假绿 (旧调法的坑).
    """
    result = subprocess.run(
        ["uv", "run", "mypy", "src", *_MYPY_FLAGS],
        cwd=str(pkg_dir),
        env={**os.environ, "MYPYPATH": "src"},
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = result.stdout + result.stderr
    m = re.search(r"Found (\d+) errors?", out)
    if m:
        return int(m.group(1))
    if result.returncode:
        raise RuntimeError(f"mypy failed for {pkg_dir}: {out.strip()}")
    return 0


def _iter_packages() -> list[Path]:
    """扫有 src/ 的包 (跳过无 src 的占位)."""
    if not PACKAGES_DIR.exists():
        print(f"❌ packages/ 目录不存在: {PACKAGES_DIR}", file=sys.stderr)
        return []
    return sorted(p for p in PACKAGES_DIR.iterdir() if p.is_dir() and (p / "src").exists())


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_baseline(path: Path) -> dict:
    if not path.exists():
        print(f"⚠️  baseline 文件不存在: {path}", file=sys.stderr)
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_baseline(path: Path, results: list[tuple[str, int]]) -> None:
    """刷新 baseline (保留 meta, 更新 entries + totals + updated_at)."""
    base = _load_baseline(path)
    entries = {name: count for name, count in sorted(results)}
    with_errors = sum(1 for _, c in results if c > 0)
    base.update(
        {
            "updated_at": _utc_now(),
            "entries": entries,
            "totals": {
                "total_errors": sum(c for _, c in results),
                "packages_with_errors": with_errors,
                "packages_clean": len(results) - with_errors,
            },
        }
    )
    path.write_text(yaml.safe_dump(base, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")


def run_report(top: int, as_json: bool) -> int:
    """真相报表: 每包错误数."""
    packages = _iter_packages()
    if not packages:
        return 1
    # (package_name, error_count) — tuple 让 sum/sorted 类型推断精确 (mypy strict 友好)
    results: list[tuple[str, int]] = []
    for pkg in packages:
        count = count_mypy_errors(pkg)
        results.append((pkg.name, count))
        if not as_json:
            print(f"  {pkg.name}: {count} errors")

    total = sum(c for _, c in results)
    if as_json:
        payload = {"total": total, "packages": [{"package": n, "errors": c} for n, c in results]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"\nTotal: {total} errors across {len(results)} packages")
    print(f"\nTop {top} packages by error count:")
    for name, count in sorted(results, key=lambda x: x[1], reverse=True)[:top]:
        print(f"  {name}: {count}")
    return 0


def run_gate(baseline_file: Path, update: bool) -> int:
    """Regression gate: 任一包错误数超 baseline → exit 1.

    DRY 复用 direct-io-baseline 范式 (卡增量, 不卡存量). 存量 baseline 见 mypy-baseline.yaml.
    """
    packages = _iter_packages()
    if not packages:
        return 1
    baseline = _load_baseline(baseline_file)
    base_entries = baseline.get("entries") or {}
    base_total = sum(int(v) for v in base_entries.values())

    results: list[tuple[str, int]] = []
    regressions: list[tuple[str, int, int]] = []  # (pkg, current, baseline)
    for pkg in packages:
        count = count_mypy_errors(pkg)
        results.append((pkg.name, count))
        base = int(base_entries.get(pkg.name, 0))
        if count > base:
            regressions.append((pkg.name, count, base))

    if update:
        _write_baseline(baseline_file, results)
        new_total = sum(c for _, c in results)
        print(f"✅ baseline 已刷新: {base_total} → {new_total} errors → {baseline_file.name}")
        return 0

    current_total = sum(c for _, c in results)
    print(f"=== mypy regression gate (baseline {base_total} → current {current_total}) ===")
    if regressions:
        print(f"❌ {len(regressions)} 包回归超 baseline:")
        for name, cur, base in regressions:
            print(f"  🔴 {name}: {cur} > baseline {base} (+{cur - base})")
        print("\n  修复后用 `make typecheck-gate-update` 降 baseline; 误报 (mypy 版本漂移) 同样刷新.")
        return 1
    print(f"✅ 无回归 (current {current_total} <= baseline {base_total})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-package mypy error report + regression gate")
    parser.add_argument("--top", type=int, default=10, help="report: 显示 top N 包 (默认 10)")
    parser.add_argument("--json", action="store_true", help="report: JSON 输出")
    parser.add_argument("--baseline", type=Path, help="gate 模式: 指定 baseline 文件")
    parser.add_argument("--update", action="store_true", help="gate 模式: 刷新 baseline (非 gate)")
    args = parser.parse_args()

    if args.baseline:
        return run_gate(args.baseline, args.update)
    return run_report(args.top, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
