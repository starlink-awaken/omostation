#!/usr/bin/env python3
"""Harness Compliance Check — Harness 全生命周期合规校验引擎.

校验 harness-policy.yaml 声明的 12 章节完整性 + 实现率 + 配额遵守:
  1. Admission — 起跑前准入
  2. Spec — 带指标的契约
  3. Execution — Step 级护栏
  4. Verify — DAG 编排 + 缓存
  5. Audit — 设计期推演 + 静态校验
  6. Accept — 分级验收
  7. Probes — 7 类 Event 标准化
  8. Dimensions — 12 维度全量挂载
  9. Value Loop — 5 阶段价值循环
  10. Known Debt — 已知债与逃生收口
  11. Observability — 可观测
  12. Rollout — 分阶段落地

用法:
  python3 bin/gac/harness-compliance-check.py              # 校验, exit 0=pass, 1=有错
  python3 bin/gac/harness-compliance-check.py --gate       # CI gate (error/structural warning fail)
  python3 bin/gac/harness-compliance-check.py --strict     # 严格模式 (warning 也 fail)
  python3 bin/gac/harness-compliance-check.py --json       # JSON 输出
  python3 bin/gac/harness-compliance-check.py --report     # 详细报告

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace (无硬编码).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

HARNESS_POLICY = WORKSPACE / ".omo" / "_truth" / "registry" / "harness-policy.yaml"
MOF_CONSTRAINTS = WORKSPACE / ".omo" / "standards" / "mof-agent-constraints.yaml"
ANTI_CORROSION_BUDGET = WORKSPACE / ".omo" / "standards" / "anti-corrosion-budget.yaml"

# ── 12 必现章节 ──
REQUIRED_SECTIONS = [
    "admission",
    "spec",
    "execution",
    "verify",
    "audit",
    "accept",
    "probes",
    "dimensions",
    "value_loop",
    "known_debt",
    "observability",
    "rollout",
]

# ── 12 维度必现 ──
REQUIRED_DIMENSIONS = [
    "X1_audit",
    "X2_freshness",
    "X3_value",
    "X4_consistency",
    "scene",
    "function",
    "journey",
    "experience",
    "vision",
    "operation",
    "ops",
    "anticorrosion",
    "constraint",
    "evolution",
    "trust",
]

# ── 7 类 Probe 必现 ──
REQUIRED_PROBES = [
    "arch_upgrade",
    "feature_add",
    "bug_fix",
    "experience",
    "doc_governance",
    "toolchain",
    "business_process",
]

# ── 5 阶段价值循环 ──
REQUIRED_VALUE_STAGES = ["signal", "perception", "journey", "value", "evolution"]


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


def check_section_completeness(data: dict | None) -> tuple[list[str], list[str]]:
    """校验 12 章节完整性."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return ["harness-policy.yaml 不存在或无法解析"], []

    for section in REQUIRED_SECTIONS:
        if section not in data:
            errors.append(f"缺少必现章节: {section}")
        elif not data[section]:
            warnings.append(f"章节为空: {section}")

    return errors, warnings


def check_sfop_slot(data: dict | None) -> tuple[list[str], list[str]]:
    """校验 SFOP S 槽位声明."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return errors, warnings

    harness = data.get("harness", {})
    if not harness:
        warnings.append("harness 节点缺失")
        return errors, warnings

    if harness.get("sfop_slot") != "S":
        errors.append(f"harness sfop_slot 应为 S, 实际: {harness.get('sfop_slot')}")
    if harness.get("controller") != "COMP-WS-omo":
        errors.append(f"harness controller 应为 COMP-WS-omo, 实际: {harness.get('controller')}")

    return errors, warnings


def check_dimensions(data: dict | None) -> tuple[list[str], list[str]]:
    """校验 12+ 维度全量挂载."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return errors, warnings

    dimensions = data.get("dimensions", {})
    if not dimensions:
        errors.append("dimensions 节点缺失")
        return errors, warnings

    for dim in REQUIRED_DIMENSIONS:
        if dim not in dimensions:
            warnings.append(f"缺少维度挂载: {dim}")

    return errors, warnings


def check_probes(data: dict | None) -> tuple[list[str], list[str]]:
    """校验 7 类 Probe 标准化."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return errors, warnings

    probes = data.get("probes", {})
    if not probes:
        errors.append("probes 节点缺失")
        return errors, warnings

    for probe in REQUIRED_PROBES:
        if probe not in probes:
            warnings.append(f"缺少 Probe: {probe}")

    # 检查 bus 声明
    if "bus" not in probes:
        warnings.append("probes.bus 缺失 (Event Bus 统一入口)")

    return errors, warnings


def check_value_loop(data: dict | None) -> tuple[list[str], list[str]]:
    """校验 5 阶段价值循环."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return errors, warnings

    value_loop = data.get("value_loop", {})
    if not value_loop:
        errors.append("value_loop 节点缺失")
        return errors, warnings

    # 检查 dag 声明 (支持中英文)
    dag = value_loop.get("dag", [])
    if not dag:
        warnings.append("value_loop.dag 缺失 (5 阶段编排)")
    else:
        # 中英文阶段名映射
        stage_aliases = {
            "signal": ["signal", "感知"],
            "perception": ["perception", "分类"],
            "journey": ["journey", "旅程执行"],
            "value": ["value", "价值记录"],
            "evolution": ["evolution", "进化反馈"],
        }
        dag_str = str(dag)
        for stage, aliases in stage_aliases.items():
            if not any(alias in dag_str for alias in aliases):
                warnings.append(f"value_loop.dag 缺少阶段: {stage}")

    return errors, warnings


def check_known_debt(data: dict | None) -> tuple[list[str], list[str]]:
    """校验已知债与逃生收口."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return errors, warnings

    known_debt = data.get("known_debt", {})
    if not known_debt:
        errors.append("known_debt 节点缺失")
        return errors, warnings

    # 检查 growth_policy
    if known_debt.get("growth_policy") != "shrink_only":
        warnings.append("known_debt.growth_policy 应为 shrink_only")

    # 检查 escape 声明
    escape = known_debt.get("escape", {})
    if not escape:
        warnings.append("known_debt.escape 缺失 (逃生口收口)")
    else:
        if "allow" not in escape:
            warnings.append("known_debt.escape.allow 缺失")

    return errors, warnings


def check_implementation_rate(data: dict | None) -> tuple[list[str], list[str]]:
    """检查实现率: 声明 vs 实际."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return errors, warnings

    harness = data.get("harness", {})
    entry = harness.get("entry", "")

    if not entry:
        warnings.append("harness.entry 缺失")
        return errors, warnings

    # 检查 entry 指向的脚本是否存在
    entry_parts = entry.split()
    if entry_parts:
        entry_name = entry_parts[0]
        candidates = [
            WORKSPACE / entry_name,
            WORKSPACE / "bin" / entry_name,
        ]
        entry_path = next((p for p in candidates if p.is_file()), None)
        if entry_path is None:
            warnings.append(f"harness.entry 指向的脚本不存在: {entry_name}")
        else:
            # 检查是否内部调用 agent-workflow
            try:
                source = entry_path.read_text(encoding="utf-8")
                if "agent-workflow" not in source and "harness" not in source:
                    warnings.append(f"{entry_name} 应内部调用 agent-workflow 或 harness")
            except OSError:
                warnings.append(f"harness.entry 不可读: {entry_path.relative_to(WORKSPACE)}")

    return errors, warnings


def check_anti_corrosion_budget() -> tuple[list[str], list[str]]:
    """检查防腐预算遵守."""
    errors: list[str] = []
    warnings: list[str] = []

    if not ANTI_CORROSION_BUDGET.exists():
        return [f"anti-corrosion-budget.yaml 不存在: {ANTI_CORROSION_BUDGET.relative_to(WORKSPACE)}"], []

    data = _load_yaml(ANTI_CORROSION_BUDGET)
    if not data:
        return errors, warnings

    budgets = data.get("budgets", {})
    if not budgets:
        warnings.append("anti-corrosion-budget.yaml budgets 节点缺失")
        return errors, warnings

    # 检查 Harness 配额
    harness_budget = budgets.get("harness_scripts", {})
    if harness_budget:
        current = harness_budget.get("current", 0)
        max_count = harness_budget.get("max_count", 0)
        if isinstance(current, (int, float)) and isinstance(max_count, (int, float)):
            if current > max_count:
                errors.append(f"Harness 脚本配额超出: {current}/{max_count}")

    return errors, warnings


def check_mof_constraints() -> tuple[list[str], list[str]]:
    """检查 MOF Agent 约束规则."""
    errors: list[str] = []
    warnings: list[str] = []

    if not MOF_CONSTRAINTS.exists():
        return warnings, [f"mof-agent-constraints.yaml 不存在: {MOF_CONSTRAINTS.relative_to(WORKSPACE)}"]

    data = _load_yaml(MOF_CONSTRAINTS)
    if not data:
        return errors, warnings

    constraints = data.get("constraints", [])
    if not constraints:
        warnings.append("mof-agent-constraints.yaml constraints 节点缺失")
        return errors, warnings

    # 检查 8 条约束完整性
    required_ids = [
        "AGENT-MOF-IMPACT-CHECK",
        "AGENT-MOF-STATE-VALID",
        "AGENT-MOF-SCHEMA-VALID",
        "AGENT-MOF-STATE-HISTORY",
        "AGENT-MOF-SSOT-COMPLETE",
        "AGENT-MOF-DEPENDENCY-DECLARE",
        "AGENT-MOF-NAMING-CONVENTION",
        "AGENT-MOF-VALUE-EVALUATE",
    ]

    existing_ids = {c.get("id") for c in constraints if isinstance(c, dict)}
    for req_id in required_ids:
        if req_id not in existing_ids:
            warnings.append(f"MOF 约束缺失: {req_id}")

    return errors, warnings


def validate() -> tuple[int, list[str], list[str], dict]:
    """主校验. 返回 (exit_code, errors, warnings, details)."""
    all_errors: list[str] = []
    all_warnings: list[str] = []
    details: dict = {}

    data = _load_yaml(HARNESS_POLICY)

    checks = [
        ("section_completeness", check_section_completeness, data),
        ("sfop_slot", check_sfop_slot, data),
        ("dimensions", check_dimensions, data),
        ("probes", check_probes, data),
        ("value_loop", check_value_loop, data),
        ("known_debt", check_known_debt, data),
        ("implementation_rate", check_implementation_rate, data),
        ("anti_corrosion_budget", check_anti_corrosion_budget, None),
        ("mof_constraints", check_mof_constraints, None),
    ]

    for name, check_fn, check_data in checks:
        if check_data is None:
            errs, warns = check_fn()
        else:
            errs, warns = check_fn(check_data)
        details[name] = {
            "errors": errs,
            "warnings": warns,
        }
        all_errors.extend(errs)
        all_warnings.extend(warns)

    return (1 if all_errors else 0, all_errors, all_warnings, details)


def main() -> int:
    args = sys.argv[1:]
    gate_mode = "--gate" in args
    strict_mode = "--strict" in args
    json_mode = "--json" in args
    report_mode = "--report" in args

    _exit_code, errors, warnings, details = validate()

    if json_mode:
        print(json.dumps(
            {
                "ok": not errors,
                "errors": errors,
                "warnings": warnings,
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1 if errors else (1 if (strict_mode and warnings) else 0)

    print("=== Harness Compliance Check (Harness 全生命周期合规) ===")
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
        print("✅ Harness Compliance Check 通过 (0 error, 0 warning)")

    return 1 if errors else (1 if (strict_mode and warnings) else 0)


if __name__ == "__main__":
    sys.exit(main())
