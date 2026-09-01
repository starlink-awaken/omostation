#!/usr/bin/env python3
"""Harness Constraint Enforcer — 统一约束与驱动机制.

整合所有 Harness 检查引擎，提供单一入口:
  - architecture-check.py (架构合规)
  - harness-compliance-check.py (Harness 全生命周期)
  - harness-mof-bridge.py (MOF 约束联动)
  - harness-omo-bridge.py (OMO 状态同步)

驱动机制:
  - 编辑前: pre-edit hook → 影响分析 + 状态转换
  - 提交前: pre-commit hook → 全量架构 + GaC
  - Push 前: pre-push hook → Harness/MOF/SFOP 深度校验
  - CI: ci_gate → 全量并行校验

用法:
  python3 bin/gac/harness-constraint-enforcer.py              # 全量执行
  python3 bin/gac/harness-constraint-enforcer.py --pre-edit   # 编辑前检查
  python3 bin/gac/harness-constraint-enforcer.py --pre-commit # 提交前检查
  python3 bin/gac/harness-constraint-enforcer.py --pre-push   # Push 前检查
  python3 bin/gac/harness-constraint-enforcer.py --ci         # CI gate
  python3 bin/gac/harness-constraint-enforcer.py --json       # JSON 输出

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
BIN_GAC = WORKSPACE / "bin" / "gac"

# ── 检查引擎注册表 ──
ENGINES = {
    "architecture": {
        "script": BIN_GAC / "architecture-check.py",
        "description": "架构合规校验 (7 项标准文件)",
        "modes": ["pre_edit", "pre_commit", "pre_push", "ci"],
    },
    "harness_compliance": {
        "script": BIN_GAC / "harness-compliance-check.py",
        "description": "Harness 全生命周期合规 (12 章节)",
        "modes": ["pre_push", "ci"],
    },
    "mof_bridge": {
        "script": BIN_GAC / "harness-mof-bridge.py",
        "description": "MOF 约束联动 (8 条规则)",
        "modes": ["pre_edit", "pre_push", "ci"],
    },
    "omo_bridge": {
        "script": BIN_GAC / "harness-omo-bridge.py",
        "description": "OMO 状态同步 (4 项同步)",
        "modes": ["pre_commit", "pre_push", "ci"],
    },
}


def run_engine(script: Path, *, json_mode: bool = True, timeout: int = 60) -> tuple[int, dict | None, str]:
    """运行检查引擎. 返回 (exit_code, json_data, stderr)."""
    if not script.exists():
        return 0, None, f"脚本不存在: {script.relative_to(WORKSPACE)}"

    cmd = [sys.executable, str(script)]
    if json_mode:
        cmd.append("--json")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE),
            timeout=timeout,
        )
        json_data = None
        if json_mode and result.stdout:
            try:
                json_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        return result.returncode, json_data, result.stderr
    except subprocess.TimeoutExpired:
        return 1, None, f"超时 ({timeout}s): {script.name}"
    except OSError as e:
        return 1, None, f"执行失败: {e}"


def run_mode(mode: str, *, json_output: bool = False) -> tuple[int, list[str], list[str], dict]:
    """按模式运行检查. 返回 (exit_code, errors, warnings, details)."""
    all_errors: list[str] = []
    all_warnings: list[str] = []
    details: dict = {}

    for name, engine in ENGINES.items():
        if mode not in engine["modes"]:
            continue

        script = engine["script"]
        exit_code, data, stderr = run_engine(script)

        engine_errors: list[str] = []
        engine_warnings: list[str] = []

        if data:
            engine_errors = data.get("errors", [])
            engine_warnings = data.get("warnings", [])
        elif exit_code != 0:
            engine_errors = [stderr or f"{name} 检查失败 (exit {exit_code})"]

        details[name] = {
            "description": engine["description"],
            "script": str(script.relative_to(WORKSPACE)),
            "exit_code": exit_code,
            "errors": engine_errors,
            "warnings": engine_warnings,
        }
        all_errors.extend(engine_errors)
        all_warnings.extend(engine_warnings)

    return (1 if all_errors else 0, all_errors, all_warnings, details)


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args

    # 确定模式
    mode = "ci"  # 默认
    if "--pre-edit" in args:
        mode = "pre_edit"
    elif "--pre-commit" in args:
        mode = "pre_commit"
    elif "--pre-push" in args:
        mode = "pre_push"
    elif "--ci" in args:
        mode = "ci"

    _exit_code, errors, warnings, details = run_mode(mode)

    if json_mode:
        print(json.dumps(
            {
                "ok": not errors,
                "mode": mode,
                "errors": errors,
                "warnings": warnings,
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1 if errors else 0

    print(f"=== Harness Constraint Enforcer (统一约束与驱动) ===")
    print(f"模式: {mode}")
    print()

    for name, detail in details.items():
        status = "PASS" if not detail["errors"] else "FAIL"
        print(f"[{status}] {name} — {detail['description']}")
        for e in detail["errors"]:
            print(f"  ❌ {e}")
        for w in detail["warnings"]:
            print(f"  ⚠️  {w}")

    print()
    if errors:
        print(f"❌ {len(errors)} 错误:")
        for e in errors:
            print(f"  - {e}")

    if warnings:
        print(f"⚠️  {len(warnings)} 警告:")
        for w in warnings:
            print(f"  - {w}")

    if not errors and not warnings:
        print("✅ Harness Constraint Enforcer 通过 (0 error, 0 warning)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
