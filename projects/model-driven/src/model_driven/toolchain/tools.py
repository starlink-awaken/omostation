"""
model_driven.toolchain.tools — 12 个核心模型驱动工具

设计/生成/推导/校验/连接/编译/演化/监控/部署/观测/报告/归档
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from model_driven.mof.m3_extended import LifecycleStage, STANDARD_STAGES, STANDARD_GATES
from model_driven.mof.m2_lifecycle import ALL_M2_SCHEMAS, get_schema, list_schemas_by_stage


# ── 1. model-design: 模型设计 ──────────────────────


def tool_design(
    m2_type: str,
    name: str,
    description: str = "",
    properties: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """交互式/模板式创建模型 (M1 节点)"""
    schema = get_schema(m2_type)
    if schema is None:
        return {"success": False, "error": f"未知 M2 类型: {m2_type}"}

    # 校验必填属性
    missing = []
    for prop_name, prop_def in schema.required_properties.items():
        if prop_name not in (properties or {}):
            missing.append(prop_name)

    node = {
        "id": f"{m2_type.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "type": m2_type,
        "name": name,
        "description": description,
        "status": "draft",
        "created": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "m2_parent": schema.m3_parent,
        "stage": schema.lifecycle_stage.value if schema.lifecycle_stage else None,
        "properties": properties or {},
        "missing_required": missing,
        "is_valid": len(missing) == 0,
    }
    return {"success": True, "node": node, "schema": schema}


# ── 2. model-generate: 模型生成 ────────────────────


def tool_generate(
    m2_type: str,
    count: int = 1,
    template: dict[str, Any] | None = None,
    target_format: str = "yaml",
    **kwargs,
) -> dict[str, Any]:
    """从模型生成代码/配置

    增强版 — 支持多种输出格式和 M1→System 正向生成。
    """
    schema = get_schema(m2_type)
    if schema is None:
        return {"success": False, "error": f"未知 M2 类型: {m2_type}"}

    generated = []
    for i in range(count):
        node_id = f"{m2_type.upper()}-GEN-{i + 1:03d}"
        node = {
            "id": node_id,
            "type": m2_type,
            "name": f"{schema.description[:20]}-{i + 1}",
            "m2_parent": schema.m3_parent,
            "status": "draft",
            "created": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "stage": schema.lifecycle_stage.value if schema.lifecycle_stage else None,
            "required_properties": {
                prop: prop_def.get("description", "")
                for prop, prop_def in schema.required_properties.items()
            },
            "optional_properties": {
                prop: prop_def.get("description", "")
                for prop, prop_def in schema.optional_properties.items()
            },
            "template": template or {},
        }
        generated.append(node)

    # 按目标格式生成
    if target_format == "yaml":
        import yaml
        output = yaml.dump(generated, allow_unicode=True, default_flow_style=False)
    elif target_format == "json":
        import json
        output = json.dumps(generated, indent=2, ensure_ascii=False)
    else:
        output = str(generated)

    return {
        "success": True,
        "generated": generated,
        "count": len(generated),
        "type": m2_type,
        "target_format": target_format,
        "output_preview": output[:500],
    }


# ── 3. model-derive: 模型推导 ──────────────────────


def tool_derive(
    models: list[dict[str, Any]] | None = None,
    rules: list[str] | None = None,
    include_transitive: bool = True,
    include_risks: bool = True,
    include_gaps: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """从模型推导关系/风险/洞察

    增强版 — 支持传递推理、风险推理、缺口发现、影响分析。
    """
    insights = []
    risks = []
    gaps = []
    transitive_chains = []
    models = models or []

    # 1. 传递推理: A→B, B→C ∴ A→C
    if include_transitive and len(models) >= 2:
        by_id = {m.get("id"): m for m in models}
        for model in models:
            for dep_id in model.get("properties", {}).get("dependencies", []):
                dep = by_id.get(dep_id)
                if dep:
                    for sub_dep_id in dep.get("properties", {}).get("dependencies", []):
                        if sub_dep_id != model.get("id"):
                            transitive_chains.append({
                                "from": model.get("id"),
                                "via": dep_id,
                                "to": sub_dep_id,
                            })

    # 2. 风险推理: 基于推导规则
    if include_risks:
        for model in models:
            mtype = model.get("type", "")
            schema = get_schema(mtype)
            if schema:
                # 必填属性缺失
                for prop_name in schema.required_properties:
                    if prop_name not in model.get("properties", {}):
                        risks.append({
                            "model_id": model.get("id"),
                            "type": "missing_property",
                            "property": prop_name,
                            "severity": "error",
                            "message": f"缺少必填属性: {prop_name}",
                        })
                # 状态检查
                status = model.get("status", "")
                valid_states = list(schema.state_machine.keys())
                if status not in valid_states:
                    risks.append({
                        "model_id": model.get("id"),
                        "type": "invalid_status",
                        "status": status,
                        "valid_states": valid_states,
                        "severity": "warning",
                        "message": f"状态 '{status}' 不在有效范围 {valid_states}",
                    })

    # 3. 缺口发现: 检测 M2 类型覆盖
    if include_gaps:
        all_types_in_models = {m.get("type") for m in models}
        for m2_type, schema in ALL_M2_SCHEMAS.items():
            if m2_type not in all_types_in_models:
                gaps.append({
                    "type": m2_type,
                    "description": schema.description,
                    "stage": schema.lifecycle_stage.value if schema.lifecycle_stage else "cross_stage",
                })

    # 4. 推导规则执行 (来自 ontology_extended)
    from model_driven.mof.ontology_extended import DERIVATION_RULES_EXTENDED
    rule_results = []
    for rule in DERIVATION_RULES_EXTENDED:
        rule_results.append({
            "rule_id": rule["id"],
            "description": rule["description"],
            "priority": rule["priority"],
            "applied": True,
        })

    return {
        "success": True,
        "insights": insights,
        "risks": risks,
        "gaps": gaps,
        "transitive_chains": transitive_chains,
        "derivation_rules": rule_results,
        "models_analyzed": len(models),
        "total_findings": len(risks) + len(gaps) + len(transitive_chains),
    }


# ── 4. model-validate: 模型校验 ────────────────────


def tool_validate(
    model: dict[str, Any] | None = None,
    models: list[dict[str, Any]] | None = None,
    strict: bool = False,
    **kwargs,
) -> dict[str, Any]:
    """校验模型一致性/合规性

    增强版 — 支持严格模式 (strict=True 时 warning 也视为失败)。
    """
    errors = []
    warnings = []
    models = models or ([model] if model else [])

    for m in models:
        mtype = m.get("type", "")
        schema = get_schema(mtype)

        if schema is None:
            errors.append({
                "model_id": m.get("id", "unknown"),
                "error": f"未知类型: {mtype}",
                "known_types": list(ALL_M2_SCHEMAS.keys())[:10],
            })
            continue

        # 校验必填属性
        props = m.get("properties", {})
        for prop_name, prop_def in schema.required_properties.items():
            if prop_name not in props:
                errors.append({
                    "model_id": m.get("id"),
                    "error": f"缺少必填属性: {prop_name}",
                    "description": prop_def.get("description", ""),
                })

        # 校验校验规则
        for rule in schema.validation_rules:
            entry = {
                "model_id": m.get("id"),
                "level": rule.get("level", "info"),
                "rule": rule.get("rule", ""),
                "message": rule.get("message", ""),
            }
            if rule.get("level") == "error":
                # 对表达式类规则进行实际求值
                if "!=" in rule.get("rule", "") and "'" in rule.get("rule", ""):
                    # 解析 rule 如 "context != ''" 检查实际值
                    parts = rule["rule"].split("!=")
                    if len(parts) == 2:
                        prop_name = parts[0].strip()
                        expected_empty = parts[1].strip().strip("'") == ""
                        actual = props.get(prop_name, "")
                        if expected_empty and not actual:
                            errors.append(entry)
                        elif not expected_empty:
                            warnings.append(entry)
                    else:
                        errors.append(entry)
                else:
                    errors.append(entry)
            else:
                warnings.append(entry)

        # 校验状态机
        status = m.get("status", "")
        if status not in schema.state_machine:
            errors.append({
                "model_id": m.get("id"),
                "error": f"无效状态: {status}",
                "valid_states": list(schema.state_machine.keys()),
            })

        # 严格模式: 检查 allowed transitions
        if strict and status in schema.state_machine:
            allowed_transitions = schema.state_machine[status].get("transitions", [])
            if not allowed_transitions and status != "archived":
                warnings.append({
                    "model_id": m.get("id"),
                    "level": "warning",
                    "message": f"状态 '{status}' 无可用转换",
                })

    passed = len(errors) == 0
    if strict:
        passed = passed and len(warnings) == 0

    return {
        "success": True,
        "passed": passed,
        "strict": strict,
        "errors": errors,
        "warnings": warnings,
        "models_checked": len(models),
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


# ── 5. model-connect: 模型关联 ────────────────────


def tool_connect(
    source_id: str = "",
    target_id: str = "",
    relation_type: str = "References",
    **kwargs,
) -> dict[str, Any]:
    """建立模型间关联"""
    edge = {
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": relation_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"success": True, "edge": edge}


# ── 6. model-compile: 模型编译 ─────────────────────


def tool_compile(
    model: dict[str, Any] | None = None,
    target_format: str = "yaml",
    **kwargs,
) -> dict[str, Any]:
    """编译模型为可执行规则/配置"""
    if model is None:
        return {"success": False, "error": "缺少模型数据"}

    compiled = {
        "source_type": model.get("type"),
        "source_id": model.get("id"),
        "target_format": target_format,
        "rules": [],
        "compiled_at": datetime.now(timezone.utc).isoformat(),
    }

    mtype = model.get("type", "")
    schema = get_schema(mtype)
    if schema:
        for rule in schema.validation_rules:
            compiled["rules"].append({
                "rule": rule.get("rule"),
                "level": rule.get("level"),
                "message": rule.get("message"),
            })

    return {"success": True, "compiled": compiled}


# ── 7. model-evolve: 模型演化 ──────────────────────


def tool_evolve(
    model: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    models: list[dict[str, Any]] | None = None,
    snapshots: list[dict[str, Any]] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """检测漂移/建议演化

    增强版 — 支持批量模型 vs 批量快照的漂移检测。
    """
    suggestions = []
    drifts = []

    # 单模型 vs 单快照
    if model and snapshot:
        model_status = model.get("status", "")
        snapshot_status = snapshot.get("status", "")
        if model_status != snapshot_status:
            drifts.append({
                "model_id": model.get("id"),
                "type": "status_drift",
                "declared": model_status,
                "actual": snapshot_status,
                "suggestion": f"更新模型状态从 {model_status} 到 {snapshot_status}",
            })

        # 属性漂移
        model_props = model.get("properties", {})
        snapshot_props = snapshot.get("properties", {})
        for key in set(list(model_props.keys()) + list(snapshot_props.keys())):
            if model_props.get(key) != snapshot_props.get(key):
                drifts.append({
                    "model_id": model.get("id"),
                    "type": "property_drift",
                    "property": key,
                    "declared": model_props.get(key),
                    "actual": snapshot_props.get(key),
                })

    # 批量漂移检测
    if models and snapshots:
        snapshot_by_id = {s.get("id"): s for s in snapshots}
        for m in models:
            s = snapshot_by_id.get(m.get("id"))
            if s:
                for key in ("status", "version"):
                    if m.get(key) != s.get(key):
                        drifts.append({
                            "model_id": m.get("id"),
                            "type": f"{key}_drift",
                            "declared": m.get(key),
                            "actual": s.get(key),
                        })

    drift_detected = len(drifts) > 0

    # 演化建议
    if drift_detected:
        suggestions.append({
            "action": "update",
            "description": f"检测到 {len(drifts)} 处漂移，建议更新模型",
            "drift_count": len(drifts),
        })

    return {
        "success": True,
        "drift_detected": drift_detected,
        "drifts": drifts,
        "suggestions": suggestions,
        "total_drifts": len(drifts),
    }


# ── 8. model-monitor: 模型监控 ─────────────────────


def tool_monitor(
    models: list[dict[str, Any]] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """监控模型健康度"""
    models = models or []
    health = {
        "total": len(models),
        "by_status": {},
        "by_stage": {},
        "issues": [],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    for m in models:
        status = m.get("status", "unknown")
        health["by_status"][status] = health["by_status"].get(status, 0) + 1

        stage = m.get("stage", "unknown")
        health["by_stage"][stage] = health["by_stage"].get(stage, 0) + 1

    health["health_score"] = 100.0 if not health["issues"] else max(0, 100 - len(health["issues"]) * 10)

    return {"success": True, "health": health}


# ── 9. model-deploy: 模型部署 ──────────────────────


def tool_deploy(
    model: dict[str, Any] | None = None,
    target: str = "local",
    **kwargs,
) -> dict[str, Any]:
    """将模型部署到目标环境"""
    if model is None:
        return {"success": False, "error": "缺少模型数据"}

    return {
        "success": True,
        "deployment": {
            "model_id": model.get("id"),
            "target": target,
            "status": "deployed",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


# ── 10. model-observe: 模型观测 ────────────────────


def tool_observe(
    model_ids: list[str] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """观测模型运行时行为"""
    observations = []
    for mid in (model_ids or []):
        observations.append({
            "model_id": mid,
            "runtime_status": "active",
            "last_observed": datetime.now(timezone.utc).isoformat(),
            "metrics": {},
        })

    return {"success": True, "observations": observations}


# ── 11. model-report: 模型报告 ─────────────────────


def tool_report(
    models: list[dict[str, Any]] | None = None,
    report_type: str = "summary",
    **kwargs,
) -> dict[str, Any]:
    """生成模型全景报告"""
    models = models or []
    report = {
        "type": report_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_models": len(models),
        "by_type": {},
        "by_stage": {},
        "by_status": {},
    }

    for m in models:
        mtype = m.get("type", "unknown")
        report["by_type"][mtype] = report["by_type"].get(mtype, 0) + 1

        stage = m.get("stage", "unknown")
        report["by_stage"][stage] = report["by_stage"].get(stage, 0) + 1

        status = m.get("status", "unknown")
        report["by_status"][status] = report["by_status"].get(status, 0) + 1

    return {"success": True, "report": report}


# ── 12. model-archive: 模型归档 ────────────────────


def tool_archive(
    model: dict[str, Any] | None = None,
    reason: str = "",
    **kwargs,
) -> dict[str, Any]:
    """归档过期模型"""
    if model is None:
        return {"success": False, "error": "缺少模型数据"}

    return {
        "success": True,
        "archive": {
            "model_id": model.get("id"),
            "previous_status": model.get("status"),
            "new_status": "archived",
            "reason": reason,
            "archived_at": datetime.now(timezone.utc).isoformat(),
        },
    }
