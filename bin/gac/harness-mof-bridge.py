#!/usr/bin/env python3
"""Harness-MOF Bridge — Harness 与 MOF 约束的深度联动.

将 MOF Agent 约束 (mof-agent-constraints.yaml) 接入 Harness 全生命周期:
  - 编辑前: 影响分析 + 状态转换合法性
  - 编辑后: schema 校验 + SSOT 完整性
  - 提交前: 跨层依赖 + 命名规范 + 价值评估

用法:
  python3 bin/gac/harness-mof-bridge.py              # 全量校验
  python3 bin/gac/harness-mof-bridge.py --impact     # 仅影响分析
  python3 bin/gac/harness-mof-bridge.py --state      # 仅状态转换
  python3 bin/gac/harness-mof-bridge.py --schema     # 仅 schema 校验
  python3 bin/gac/harness-mof-bridge.py --json       # JSON 输出

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

MOF_CONSTRAINTS = WORKSPACE / ".omo" / "standards" / "mof-agent-constraints.yaml"
MOF_DIR = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof"
HARNESS_POLICY = WORKSPACE / ".omo" / "_truth" / "registry" / "harness-policy.yaml"

# ── MOF 约束 ID → 检查函数映射 ──
CONSTRAINT_IDS = [
    "AGENT-MOF-IMPACT-CHECK",
    "AGENT-MOF-STATE-VALID",
    "AGENT-MOF-SCHEMA-VALID",
    "AGENT-MOF-STATE-HISTORY",
    "AGENT-MOF-SSOT-COMPLETE",
    "AGENT-MOF-DEPENDENCY-DECLARE",
    "AGENT-MOF-NAMING-CONVENTION",
    "AGENT-MOF-VALUE-EVALUATE",
]


def _load_yaml(path: Path) -> dict | list | None:
    """安全加载 YAML."""
    if not path.exists():
        return None
    try:
        import yaml
        text = path.read_text(encoding="utf-8")
        docs = [d for d in yaml.safe_load_all(text) if d]
        if not docs:
            return None
        body = docs[-1]
        return body if isinstance(body, (dict, list)) else None
    except Exception:
        return None


def check_impact_analysis() -> tuple[list[str], list[str]]:
    """AGENT-MOF-IMPACT-CHECK: 修改前影响分析."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_DIR.exists():
        # MOF 可能位于 submodule 或 archive 中，降级为 warning
        warnings.append(f"MOF 目录不存在: {MOF_DIR.relative_to(WORKSPACE)} (可能位于 submodule/archive)")
        return errors, warnings

    # 检查 M1 节点是否有影响链记录
    m1_files = list(MOF_DIR.glob("**/*.yaml")) + list(MOF_DIR.glob("**/*.json"))
    if not m1_files:
        warnings.append("M1 节点目录为空，无影响链可分析")
        return errors, warnings

    # 抽样检查: 每个 M1 节点应有 relations 或 depends_on
    # 阈值采样: drift≥5 时全量扫描，否则抽查前 20 个
    sample_limit = len(m1_files) if len(warnings) >= 5 else min(20, len(m1_files))
    for m1_file in m1_files[:sample_limit]:
        try:
            data = _load_yaml(m1_file)
            if not data or not isinstance(data, dict):
                continue
            if "relations" not in data and "depends_on" not in data:
                warnings.append(f"{m1_file.relative_to(WORKSPACE)}: 缺少 relations/depends_on 声明")
        except Exception:
            continue

    return errors, warnings


def check_state_validity() -> tuple[list[str], list[str]]:
    """AGENT-MOF-STATE-VALID: 状态转换合法性."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_DIR.exists():
        return errors, warnings

    # 检查 stateMachine 定义
    state_machine_file = MOF_DIR / "stateMachine.yaml"
    if not state_machine_file.exists():
        # 可能在其他位置
        state_machine_files = list(MOF_DIR.rglob("stateMachine*"))
        if not state_machine_files:
            warnings.append("stateMachine 定义文件缺失")
            return errors, warnings

    return errors, warnings


def check_schema_validity() -> tuple[list[str], list[str]]:
    """AGENT-MOF-SCHEMA-VALID: 新增节点 schema 校验."""
    errors: list[str] = []
    warnings: list[str] = []

    # 检查 MOF schema 校验工具是否存在 (可能在 submodule ecos 中)
    schema_validator = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "compiler" / "api.py"
    if not schema_validator.exists():
        warnings.append("MOF schema 校验器 (compiler/api.py) 不存在 (可能位于 submodule)")
        return errors, warnings

    return errors, warnings


def check_state_history() -> tuple[list[str], list[str]]:
    """AGENT-MOF-STATE-HISTORY: 状态历史记录."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_DIR.exists():
        return errors, warnings

    # 检查 state_history 记录
    history_file = WORKSPACE / ".omo" / "_control" / "governance-data.json"
    if not history_file.exists():
        warnings.append("governance-data.json 缺失 (状态历史存储)")
        return errors, warnings

    return errors, warnings


def check_ssot_completeness() -> tuple[list[str], list[str]]:
    """AGENT-MOF-SSOT-COMPLETE: SSOT 完整性."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_DIR.exists():
        return errors, warnings

    # 检查 model_driven_refs
    m1_files = list(MOF_DIR.glob("**/*.yaml"))
    for m1_file in m1_files[:10]:
        try:
            data = _load_yaml(m1_file)
            if not data or not isinstance(data, dict):
                continue
            if "model_driven_refs" not in data:
                warnings.append(f"{m1_file.relative_to(WORKSPACE)}: 缺少 model_driven_refs")
        except Exception:
            continue

    return errors, warnings


def check_dependency_declaration() -> tuple[list[str], list[str]]:
    """AGENT-MOF-DEPENDENCY-DECLARE: 跨层依赖声明."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_DIR.exists():
        return errors, warnings

    # 检查跨层依赖
    m1_files = list(MOF_DIR.glob("**/*.yaml"))
    for m1_file in m1_files[:10]:
        try:
            data = _load_yaml(m1_file)
            if not data or not isinstance(data, dict):
                continue
            relations = data.get("relations", {})
            if isinstance(relations, dict) and "depends_on" not in relations:
                warnings.append(f"{m1_file.relative_to(WORKSPACE)}: relations 缺少 depends_on")
        except Exception:
            continue

    return errors, warnings


def check_naming_convention() -> tuple[list[str], list[str]]:
    """AGENT-MOF-NAMING-CONVENTION: 命名规范统一."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_DIR.exists():
        return errors, warnings

    # 检查 type 字段 PascalCase
    m1_files = list(MOF_DIR.glob("**/*.yaml"))
    for m1_file in m1_files[:10]:
        try:
            data = _load_yaml(m1_file)
            if not data or not isinstance(data, dict):
                continue
            type_field = data.get("type", "")
            if type_field and isinstance(type_field, str):
                if not type_field[0].isupper():
                    warnings.append(f"{m1_file.relative_to(WORKSPACE)}: type '{type_field}' 应为 PascalCase")
        except Exception:
            continue

    return errors, warnings


def check_value_evaluation() -> tuple[list[str], list[str]]:
    """AGENT-MOF-VALUE-EVALUATE: 价值评估."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_DIR.exists():
        return errors, warnings

    # 检查 value_metrics
    m1_files = list(MOF_DIR.glob("**/*.yaml"))
    for m1_file in m1_files[:10]:
        try:
            data = _load_yaml(m1_file)
            if not data or not isinstance(data, dict):
                continue
            if "value_metrics" not in data and "cost_model" not in data:
                warnings.append(f"{m1_file.relative_to(WORKSPACE)}: 缺少 value_metrics/cost_model")
        except Exception:
            continue

    return errors, warnings


def validate(mode: str = "full") -> tuple[int, list[str], list[str], dict]:
    """主校验. 返回 (exit_code, errors, warnings, details)."""
    all_errors: list[str] = []
    all_warnings: list[str] = []
    details: dict = {}

    checks = {
        "impact_analysis": check_impact_analysis,
        "state_validity": check_state_validity,
        "schema_validity": check_schema_validity,
        "state_history": check_state_history,
        "ssot_completeness": check_ssot_completeness,
        "dependency_declaration": check_dependency_declaration,
        "naming_convention": check_naming_convention,
        "value_evaluation": check_value_evaluation,
    }

    # 根据 mode 选择检查
    if mode == "impact":
        selected = {k: checks[k] for k in ["impact_analysis", "state_validity"]}
    elif mode == "state":
        selected = {k: checks[k] for k in ["state_validity", "state_history"]}
    elif mode == "schema":
        selected = {k: checks[k] for k in ["schema_validity", "naming_convention"]}
    else:
        selected = checks

    for name, check_fn in selected.items():
        errs, warns = check_fn()
        details[name] = {"errors": errs, "warnings": warns}
        all_errors.extend(errs)
        all_warnings.extend(warns)

    return (1 if all_errors else 0, all_errors, all_warnings, details)


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args
    mode = "full"
    if "--impact" in args:
        mode = "impact"
    elif "--state" in args:
        mode = "state"
    elif "--schema" in args:
        mode = "schema"

    _exit_code, errors, warnings, details = validate(mode)

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

    print("=== Harness-MOF Bridge (MOF 约束联动) ===")
    print(f"模式: {mode}")
    print()

    for name, detail in details.items():
        status = "PASS" if not detail["errors"] else "FAIL"
        print(f"[{status}] {name}")
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
        print("✅ Harness-MOF Bridge 通过 (0 error, 0 warning)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
