#!/usr/bin/env python3
"""Architecture Check — 架构合规校验引擎 (ADR-0190 系列, Phase 2 校验层).

校验架构标准一致性:
  - 场景卡生命周期 (scene-card-lifecycle.yaml) 5 级门控
  - 业务域分类 (business-domains.yaml) 5 域覆盖
  - 维度系统 (dimension-system.yaml) 12 维度完整性
  - 价值循环 (value-loop-standard.yaml) 5 阶段闭环
  - SSOT 索引 (architecture-ssot-index.yaml) 核心文档 + 注册表对齐

用法:
  python3 bin/gac/architecture-check.py              # 校验, exit 0=pass, 1=有错
  python3 bin/gac/architecture-check.py --gate       # CI gate (error/structural warning fail)
  python3 bin/gac/architecture-check.py --strict     # 严格模式 (warning 也 fail)
  python3 bin/gac/architecture-check.py --json       # JSON 输出 (仪表盘数据源)
  python3 bin/gac/architecture-check.py --report     # 详细报告

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace (无硬编码).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# ── 架构标准文件路径 ──
STANDARDS = {
    "scene_card_lifecycle": WORKSPACE / ".omo" / "standards" / "scene-card-lifecycle.yaml",
    "business_domains": WORKSPACE / ".omo" / "standards" / "business-domains.yaml",
    "dimension_system": WORKSPACE / ".omo" / "standards" / "dimension-system.yaml",
    "value_loop": WORKSPACE / ".omo" / "standards" / "value-loop-standard.yaml",
    "ssot_index": WORKSPACE / ".omo" / "standards" / "architecture-ssot-index.yaml",
    "anti_corrosion_budget": WORKSPACE / ".omo" / "standards" / "anti-corrosion-budget.yaml",
}

# ── Harness 策略路径 ──
HARNESS_POLICY = WORKSPACE / ".omo" / "_truth" / "registry" / "harness-policy.yaml"

# ── 核心文档路径 (SSOT 索引声明) ──
CORE_DOCS = {
    "ARCHITECTURE.md": WORKSPACE / "ARCHITECTURE.md",
    "PANORAMA.md": WORKSPACE / "docs" / "PANORAMA.md",
    "STATE.md": WORKSPACE / ".omo" / "state" / "system.yaml",
}


def _load_yaml(path: Path) -> dict | list | None:
    """安全加载 YAML (支持 frontmatter + 正文 多文档)."""
    if not path.exists():
        return None
    try:
        import yaml

        text = path.read_text(encoding="utf-8")
        docs = [d for d in yaml.safe_load_all(text) if d]
        if not docs:
            return None
        # 多文档: 取最后一个非空文档 (正文)
        body = docs[-1]
        return body if isinstance(body, (dict, list)) else None
    except Exception:
        return None


def check_scene_card_lifecycle(data: dict | None) -> tuple[list[str], list[str]]:
    """校验场景卡生命周期标准: 5 级必现 + 升级门控."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return ["scene-card-lifecycle.yaml 不存在或无法解析"], []

    lifecycle = data.get("lifecycle", {})
    if not lifecycle:
        errors.append("lifecycle 节点缺失")
        return errors, warnings

    required_tiers = ["draft", "shadow", "assisted", "supervised", "routine"]
    for tier in required_tiers:
        if tier not in lifecycle:
            errors.append(f"lifecycle 缺少 {tier} 级")
            continue
        tier_data = lifecycle[tier]
        if not isinstance(tier_data, dict):
            errors.append(f"lifecycle.{tier} 结构错误")
            continue
        if "order" not in tier_data:
            errors.append(f"lifecycle.{tier} 缺少 order 字段")
        if "can_execute" not in tier_data:
            errors.append(f"lifecycle.{tier} 缺少 can_execute 字段")

    # 升级门控: shadow 需 min_samples, assisted 需 min_samples + min_calibration
    shadow = lifecycle.get("shadow", {})
    if "min_samples" not in shadow:
        warnings.append("shadow 缺少 min_samples 升级门控")

    assisted = lifecycle.get("assisted", {})
    if "min_samples" not in assisted:
        warnings.append("assisted 缺少 min_samples 升级门控")
    if "min_calibration" not in assisted:
        warnings.append("assisted 缺少 min_calibration 升级门控")

    return errors, warnings


def check_business_domains(data: dict | None) -> tuple[list[str], list[str]]:
    """校验业务域分类标准: 5 域必现."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return ["business-domains.yaml 不存在或无法解析"], []

    domains = data.get("domains", {})
    if not domains:
        errors.append("domains 节点缺失")
        return errors, warnings

    required_domains = ["work", "health", "research", "knowledge", "governance"]
    for domain in required_domains:
        if domain not in domains:
            errors.append(f"domains 缺少 {domain} 域")
            continue
        domain_data = domains[domain]
        if not isinstance(domain_data, dict):
            errors.append(f"domains.{domain} 结构错误")
            continue
        if "name" not in domain_data:
            errors.append(f"domains.{domain} 缺少 name 字段")
        if "scenes" not in domain_data:
            warnings.append(f"domains.{domain} 缺少 scenes 列表")

    return errors, warnings


def check_dimension_system(data: dict | None) -> tuple[list[str], list[str]]:
    """校验维度系统标准: 12 维度 + 度量框架."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return ["dimension-system.yaml 不存在或无法解析"], []

    dimensions = data.get("dimensions", {})
    if not dimensions:
        errors.append("dimensions 节点缺失")
        return errors, warnings

    # 治理维度 X1-X4
    for x in ["X1_audit", "X2_freshness", "X3_value", "X4_consistency"]:
        if x not in dimensions:
            errors.append(f"dimensions 缺少治理维度 {x}")

    # 业务/运营维度 D1-D8（dimension-system v2.0.0 官方 12 维度）
    for d in ["D1_scene", "D2_function", "D3_journey", "D4_experience",
              "D5_vision", "D6_operations", "D7_maintenance", "D8_harness"]:
        if d not in dimensions:
            errors.append(f"dimensions 缺少业务维度 {d}")

    # 度量框架
    framework = data.get("measurement_framework", {})
    if not framework:
        warnings.append("measurement_framework 节点缺失")
    else:
        if "score_range" not in framework:
            warnings.append("measurement_framework 缺少 score_range")
        if "target_score" not in framework:
            warnings.append("measurement_framework 缺少 target_score")

    return errors, warnings


def check_value_loop(data: dict | None) -> tuple[list[str], list[str]]:
    """校验价值循环标准: 5 阶段 + 北极星 + 断链修复."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return ["value-loop-standard.yaml 不存在或无法解析"], []

    stages = data.get("stages", {})
    if not stages:
        errors.append("stages 节点缺失")
        return errors, warnings

    required_stages = ["signal", "perception", "journey", "value", "evolution"]
    for stage in required_stages:
        if stage not in stages:
            errors.append(f"stages 缺少 {stage} 阶段")
            continue
        stage_data = stages[stage]
        if not isinstance(stage_data, dict):
            errors.append(f"stages.{stage} 结构错误")
            continue
        if "output" not in stage_data:
            warnings.append(f"stages.{stage} 缺少 output 字段")

    # 北极星
    north_star = data.get("north_star", {})
    if not north_star:
        warnings.append("north_star 节点缺失")
    else:
        for axis in ["axis_a_time", "axis_b_decision", "axis_c_project"]:
            if axis not in north_star:
                warnings.append(f"north_star 缺少 {axis} 轴")

    # 断链修复
    broken_chains = data.get("broken_chains", {})
    if not broken_chains:
        warnings.append("broken_chains 节点缺失 (断链修复追踪)")

    return errors, warnings


def check_ssot_index(data: dict | None) -> tuple[list[str], list[str]]:
    """校验 SSOT 索引: 核心文档存在性 + 注册表路径有效性."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return ["architecture-ssot-index.yaml 不存在或无法解析"], []

    # 核心文档存在性
    core_docs = data.get("core_documents", {})
    if not core_docs:
        errors.append("core_documents 节点缺失")
    else:
        for doc_name, doc_info in core_docs.items():
            if isinstance(doc_info, dict) and "path" in doc_info:
                doc_path = WORKSPACE / doc_info["path"]
                if not doc_path.exists():
                    errors.append(f"核心文档缺失: {doc_info['path']} (声明于 core_documents.{doc_name})")

    # 标准库路径有效性
    standards = data.get("standards", {})
    if not standards:
        warnings.append("standards 节点缺失")
    else:
        for std_name, std_info in standards.items():
            if isinstance(std_info, dict) and "path" in std_info:
                std_path = WORKSPACE / std_info["path"]
                if not std_path.exists():
                    errors.append(f"标准文件缺失: {std_info['path']} (声明于 standards.{std_name})")

    # 注册表路径有效性
    registries = data.get("registries", {})
    if not registries:
        warnings.append("registries 节点缺失")
    else:
        for reg_name, reg_path in registries.items():
        # registries 可能是 str 或 dict
            actual_path = reg_path if isinstance(reg_path, str) else reg_path.get("path") if isinstance(reg_path, dict) else None
            if actual_path:
                full_path = WORKSPACE / actual_path
                if not full_path.exists():
                    warnings.append(f"注册表路径不存在: {actual_path} (声明于 registries.{reg_name})")

    return errors, warnings


def check_harness_policy() -> tuple[list[str], list[str]]:
    """检查 harness-policy.yaml 合规性 (12 章节完整性 + 实现率)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not HARNESS_POLICY.exists():
        return ["harness-policy.yaml 不存在"], []

    data = _load_yaml(HARNESS_POLICY)
    if not data:
        return ["harness-policy.yaml 无法解析"], []

    # 检查 12 章节完整性
    expected_sections = [
        "admission", "spec", "execution", "verify",
        "audit", "accept", "probes", "dimensions",
        "value_loop", "known_debt", "observability", "rollout",
    ]

    for section in expected_sections:
        if section not in data:
            warnings.append(f"缺少章节: {section}")

    # 检查 SFOP S 槽位声明
    harness = data.get("harness", {})
    if harness.get("sfop_slot") != "S":
        warnings.append("harness sfop_slot 应为 S")
    if harness.get("controller") != "COMP-WS-omo":
        warnings.append("harness controller 应为 COMP-WS-omo")

    # 检查实现率 (声明 vs 实际): harness run 应该调用 agent-workflow。
    entry = harness.get("entry", "")
    if "harness run" in entry:
        entry_name = entry.split()[0]
        candidates = (WORKSPACE / entry_name, WORKSPACE / "bin" / entry_name)
        entry_path = next((path for path in candidates if path.is_file()), candidates[0])
        try:
            entry_source = entry_path.read_text(encoding="utf-8")
        except OSError:
            warnings.append(f"harness entry 不可读: {entry_path.relative_to(WORKSPACE)}")
        else:
            if "bin/agent-workflow.py" not in entry_source:
                warnings.append("harness run 应内部调用 agent-workflow")

    return errors, warnings


def check_runtime_consistency() -> tuple[list[str], list[str]]:
    """运行时一致性检查: SFOP S 槽位唯一性."""
    errors: list[str] = []
    warnings: list[str] = []

    # 检查 SFOP S 槽位唯一性
    sfop_check = Path(__file__).parent / "check-sfop-slots.py"
    if sfop_check.exists():
        import subprocess
        result = subprocess.run(
            [sys.executable, str(sfop_check), "--json"],
            capture_output=True, text=True, cwd=str(WORKSPACE),
        )
        if result.returncode != 0:
            # 解析输出检查 S 槽位
            if "S" in result.stdout and "unique" in result.stdout.lower():
                warnings.append("SFOP S 槽位唯一性检查失败")

    return errors, warnings


def check_anti_corrosion_budget(data: dict | None) -> tuple[list[str], list[str]]:
    """检查防腐预算合规性."""
    errors: list[str] = []
    warnings: list[str] = []

    if data is None:
        return ["anti-corrosion-budget.yaml 不存在或无法解析"], []

    budgets = data.get("budgets", {})
    if not budgets:
        errors.append("budgets 节点缺失")
        return errors, warnings

    # 检查各项预算
    for budget_name, budget_info in budgets.items():
        if not isinstance(budget_info, dict):
            continue
        raw_max_count = budget_info.get("max_count", 0)
        raw_current = budget_info.get("current", 0)
        raw_alert_threshold = budget_info.get("alert_threshold", 0.9)

        def as_number(value: object) -> float | None:
            if isinstance(value, bool):
                return None
            if isinstance(value, (int, float)):
                number = float(value)
                return number if math.isfinite(number) else None
            if isinstance(value, str):
                candidate = value.strip().removeprefix("~").strip()
                try:
                    number = float(candidate)
                except ValueError:
                    return None
                return number if math.isfinite(number) else None
            return None

        max_count = as_number(raw_max_count)
        current = as_number(raw_current)
        alert_threshold = as_number(raw_alert_threshold)
        invalid = False
        for field, raw_value, parsed in (
            ("max_count", raw_max_count, max_count),
            ("current", raw_current, current),
            ("alert_threshold", raw_alert_threshold, alert_threshold),
        ):
            if parsed is None:
                errors.append(f"{budget_name}: {field} 必须是数值，实际为 {raw_value!r}")
                invalid = True
        if invalid:
            continue
        assert max_count is not None and current is not None and alert_threshold is not None
        if max_count < 0:
            errors.append(f"{budget_name}: max_count 必须大于等于 0，实际为 {raw_max_count!r}")
            continue
        if current < 0:
            errors.append(f"{budget_name}: current 必须大于等于 0，实际为 {raw_current!r}")
            continue
        if not 0 <= alert_threshold <= 1:
            errors.append(
                f"{budget_name}: alert_threshold 必须在 0 到 1 之间，实际为 {raw_alert_threshold!r}"
            )
            continue
        if current > max_count:
            errors.append(f"{budget_name}: 当前 {raw_current} 超出预算 {raw_max_count}")
        elif current > max_count * alert_threshold:
            warnings.append(
                f"{budget_name}: 当前 {raw_current} 接近预算 {raw_max_count} (阈值 {alert_threshold:.0%})"
            )

    return errors, warnings


def validate() -> tuple[int, list[str], list[str], dict]:
    """主校验. 返回 (exit_code, errors, warnings, details)."""
    all_errors: list[str] = []
    all_warnings: list[str] = []
    details: dict = {}

    checks = [
        ("scene_card_lifecycle", check_scene_card_lifecycle),
        ("business_domains", check_business_domains),
        ("dimension_system", check_dimension_system),
        ("value_loop", check_value_loop),
        ("ssot_index", check_ssot_index),
        ("anti_corrosion_budget", check_anti_corrosion_budget),
    ]

    for name, check_fn in checks:
        path = STANDARDS.get(name)
        if path:
            data = _load_yaml(path)
        else:
            data = None
        errs, warns = check_fn(data)
        details[name] = {
            "path": str(path.relative_to(WORKSPACE)) if path else "N/A",
            "exists": path.exists() if path else False,
            "errors": errs,
            "warnings": warns,
        }
        all_errors.extend(errs)
        all_warnings.extend(warns)

    # Harness 策略检查 (独立)
    errs, warns = check_harness_policy()
    details["harness_policy"] = {
        "path": str(HARNESS_POLICY.relative_to(WORKSPACE)),
        "exists": HARNESS_POLICY.exists(),
        "errors": errs,
        "warnings": warns,
    }
    all_errors.extend(errs)
    all_warnings.extend(warns)

    # 运行时一致性检查
    errs, warns = check_runtime_consistency()
    details["runtime_consistency"] = {
        "path": "runtime",
        "exists": True,
        "errors": errs,
        "warnings": warns,
    }
    all_errors.extend(errs)
    all_warnings.extend(warns)

    return (1 if all_errors else 0, all_errors, all_warnings, details)


def result_exit_code(errors: list[str], warnings: list[str], *, gate: bool, strict: bool) -> int:
    """Map findings to status while keeping budget alerts advisory in CI."""

    if errors:
        return 1
    if strict and warnings:
        return 1
    if gate:
        blocking_warnings = [warning for warning in warnings if "接近预算" not in warning]
        if blocking_warnings:
            return 1
    return 0


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
        return result_exit_code(errors, warnings, gate=gate_mode, strict=strict_mode)

    print("=== Architecture Check (架构合规校验) ===")
    print(f"校验标准数: {len(STANDARDS)}")
    print()

    for name, detail in details.items():
        status = "PASS" if not detail["errors"] else "FAIL"
        rel_path = detail["path"]
        print(f"[{status}] {name} ({rel_path})")
        if not detail["exists"]:
            print("  ⚠️  文件不存在")
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
        print("✅ Architecture Check 通过 (0 error, 0 warning)")

    return result_exit_code(errors, warnings, gate=gate_mode, strict=strict_mode)


if __name__ == "__main__":
    sys.exit(main())
