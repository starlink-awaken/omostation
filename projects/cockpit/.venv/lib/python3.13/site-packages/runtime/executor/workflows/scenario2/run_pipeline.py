#!/usr/bin/env python3
# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""场景二管道编排 — 注入冲突 → 检测 → 审议 → 合并 → 验证 + HITL。

用法:
    python3 -m runtime.executor.workflows.scenario2.run_pipeline              # 交互模式
    python3 -m runtime.executor.workflows.scenario2.run_pipeline --auto       # 自动模式
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
REPORT_DIR = PROJECT_ROOT / "data" / "scenario2"
WORKFLOWS_DIR = Path(__file__).resolve().parent


def _run(cmd: list[str], desc: str) -> tuple[int, str]:
    print(f"\n{'='*60}")
    print(f"  ▶ [{desc}]")
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.stdout:
        print(result.stdout[:1500])
    if result.stderr:
        print(f"  [stderr]: {result.stderr[:300]}")
    return result.returncode, result.stdout


def _hitl(phase: str) -> bool:
    print(f"\n{'#'*60}")
    print(f"# ⏸️  HITL: {phase}")
    print(f"# 时间: {datetime.now(UTC).isoformat()}")
    try:
        r = input("继续下一阶段？(Y/n): ").strip().lower()
        return r in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def phase1_inject(auto: bool = False) -> bool:
    print("\n=== PHASE 1: 注入冲突事实 ===")
    rc, out = _run(
        [sys.executable, str(WORKFLOWS_DIR / "inject_personal_conflicts.py")],
        "注入冲突",
    )
    if "injected" in out:
        import json as _j
        try:
            d = _j.loads(out.strip().split("\n")[0])
            print(f"  注入: {d.get('injected', 0)}, 跳过: {d.get('skipped', 0)}")
        except (IndexError, _j.JSONDecodeError, TypeError):
            pass
    if not auto and not _hitl("Phase 1: 冲突注入确认"):
        return False
    return rc == 0


def phase2_detect(auto: bool = False) -> bool:
    print("\n=== PHASE 2: 冲突检测 ===")
    rc, out = _run(
        [sys.executable, str(WORKFLOWS_DIR / "detect_conflicts.py")],
        "冲突检测",
    )
    if "冲突数" in out:
        for line in out.split("\n"):
            if "冲突数" in line:
                print(f"  {line.strip()}")
    if not auto and not _hitl("Phase 2: 冲突报告确认"):
        return False
    return rc == 0


def phase3_deliberate(auto: bool = False) -> bool:
    print("\n=== PHASE 3: Council 审议 ===")
    rc, out = _run(
        [sys.executable, str(WORKFLOWS_DIR / "run_council_deliberation.py")],
        "Council审议",
    )
    if not auto and not _hitl("Phase 3: 审议结果确认"):
        return False
    return rc == 0


def phase4_merge(auto: bool = False) -> bool:
    print("\n=== PHASE 4: 加权合并 ===")
    rc, out = _run(
        [sys.executable, str(WORKFLOWS_DIR / "apply_weighted_merge.py")],
        "加权合并",
    )
    if "更新" in out:
        for line in out.split("\n"):
            if "更新" in line:
                print(f"  {line.strip()}")
    if not auto and not _hitl("Phase 4: 合并结果确认"):
        return False
    return rc == 0


def phase5_verify(auto: bool = False) -> bool:
    print("\n=== PHASE 5: 跨会话回忆验证 ===")
    rc, out = _run(
        [sys.executable, str(WORKFLOWS_DIR / "recall_verification.py")],
        "回忆验证",
    )

    # 检查命中率
    passed = True
    if "命中率" in out:
        for line in out.split("\n"):
            if "命中率" in line and "≥80%" in line:
                passed = "✅" in line
                print(f"  命中率: {'通过' if passed else '未通过'}")

    if not auto:
        _hitl("Phase 5: 验证报告确认")
    return passed


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="场景二：跨会话上下文+事实一致性")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--phase", choices=["1", "2", "3", "4", "5"])
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    auto = args.auto

    phases = [
        ("1", "注入冲突事实", phase1_inject),
        ("2", "冲突检测", phase2_detect),
        ("3", "Council审议", phase3_deliberate),
        ("4", "加权合并", phase4_merge),
        ("5", "回忆验证", phase5_verify),
    ]

    for pid, pname, pfunc in phases:
        if args.phase and args.phase != pid:
            continue
        print(f"\n>>> Phase {pid}: {pname}")
        if not pfunc(auto):
            print(f"❌ Phase {pid} 中止")
            sys.exit(1)

    print(f"\n{'='*60}")
    print("  ✅ 场景二执行完成！")
    print(f"  报告目录: {REPORT_DIR}")


if __name__ == "__main__":
    main()
