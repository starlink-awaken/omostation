"""
model_driven.mof.ontology_extended — 本体论映射扩展

扩展 ontology.yaml，新增全生命周期阶段间的语义关系映射。
"""

from .m3_extended import LifecycleStage

# ── 阶段等价映射 ──────────────────────────────────

STAGE_EQUIVALENCES = [
    {"a": "规划态", "b": "Planning Phase", "relation": "EquivalentTo", "note": "中英文等价"},
    {"a": "设计态", "b": "Design Phase", "relation": "EquivalentTo", "note": "中英文等价"},
    {"a": "开发态", "b": "Development Phase", "relation": "EquivalentTo", "note": "中英文等价"},
    {"a": "部署态", "b": "Deployment Phase", "relation": "EquivalentTo", "note": "中英文等价"},
    {"a": "运行态", "b": "Runtime Phase", "relation": "EquivalentTo", "note": "中英文等价"},
    {"a": "运维态", "b": "Operations Phase", "relation": "EquivalentTo", "note": "中英文等价"},
    {"a": "运营态", "b": "Business Operations Phase", "relation": "EquivalentTo", "note": "中英文等价"},
]

# ── 阶段间依赖关系 ────────────────────────────────

STAGE_DEPENDENCIES = [
    {"dependent": "设计态", "depends_on": "规划态", "note": "设计依赖规划阶段的 OKR 和需求"},
    {"dependent": "开发态", "depends_on": "设计态", "note": "开发依赖设计阶段的 Spec 和 ADR"},
    {"dependent": "部署态", "depends_on": "开发态", "note": "部署依赖开发阶段的代码和测试"},
    {"dependent": "运行态", "depends_on": "部署态", "note": "运行依赖部署阶段的配置和环境"},
    {"dependent": "运维态", "depends_on": "运行态", "note": "运维依赖运行阶段的监控和告警"},
    {"dependent": "运营态", "depends_on": "运行态", "note": "运营依赖运行阶段的用户数据"},
]

# ── M2 类型到阶段的映射 ───────────────────────────

M2_TYPE_STAGE_MAPPING = {
    "roadmap": LifecycleStage.PLANNING,
    "okr": LifecycleStage.PLANNING,
    "initiative": LifecycleStage.PLANNING,
    "adr": LifecycleStage.DESIGN,
    "spec_design": LifecycleStage.DESIGN,
    "interface_contract": LifecycleStage.DESIGN,
    "code_module": LifecycleStage.DEVELOPMENT,
    "test_suite": LifecycleStage.DEVELOPMENT,
    "ci_pipeline": LifecycleStage.DEVELOPMENT,
    "deployment_config": LifecycleStage.DEPLOYMENT,
    "release_plan": LifecycleStage.DEPLOYMENT,
    "environment": LifecycleStage.DEPLOYMENT,
    "runbook": LifecycleStage.RUNTIME,
    "alert_rule": LifecycleStage.RUNTIME,
    "dashboard_config": LifecycleStage.RUNTIME,
    "incident": LifecycleStage.OPERATIONS,
    "change_request": LifecycleStage.OPERATIONS,
    "migration_plan": LifecycleStage.OPERATIONS,
    "user_journey": LifecycleStage.BUSINESS_OPS,
    "value_stream": LifecycleStage.BUSINESS_OPS,
    "feedback": LifecycleStage.BUSINESS_OPS,
    "cost_model": None,  # 全阶段
    "benefit_model": None,  # 全阶段
    "roi_analysis": None,  # 全阶段
}

# ── 推导规则 (扩展) ────────────────────────────────

DERIVATION_RULES_EXTENDED = [
    {
        "id": "DR-09",
        "description": "OKR 进度滞后 → 规划态风险",
        "rule": "if (OKR.progress < expected_progress) then Stage(planning).risk += 'behind_schedule'",
        "priority": "high",
    },
    {
        "id": "DR-10",
        "description": "ADR 未关联 Spec → 设计漂移风险",
        "rule": "if (ADR.related_specs == empty) then ADR.risk += 'orphan_decision'",
        "priority": "medium",
    },
    {
        "id": "DR-11",
        "description": "测试覆盖率低于阈值 → 开发态风险",
        "rule": "if (CodeModule.test_coverage < 80%) then Stage(development).risk += 'low_coverage'",
        "priority": "high",
    },
    {
        "id": "DR-12",
        "description": "部署无回滚计划 → 部署态风险",
        "rule": "if (ReleasePlan.rollback_plan == null) then Stage(deployment).risk += 'no_rollback'",
        "priority": "high",
    },
    {
        "id": "DR-13",
        "description": "告警规则无关联运行手册 → 运行态风险",
        "rule": "if (AlertRule.runbook_ref == null) then Stage(runtime).risk += 'no_runbook'",
        "priority": "medium",
    },
    {
        "id": "DR-14",
        "description": "事件未复盘 → 运维态风险",
        "rule": "if (Incident.status == 'resolved' and Incident.postmortem == null) then Stage(operations).risk += 'no_postmortem'",
        "priority": "medium",
    },
    {
        "id": "DR-15",
        "description": "价值流存在瓶颈 → 运营态风险",
        "rule": "if (ValueStream.bottlenecks.size > 0) then Stage(business_ops).risk += 'flow_bottleneck'",
        "priority": "medium",
    },
]

# ── 跨阶段一致性检查规则 ──────────────────────────

CROSS_STAGE_CONSISTENCY_RULES = [
    {
        "id": "CS-01",
        "description": "规划→设计一致性：所有 Spec 必须有对应 OKR",
        "check": "for each Spec: exists OKR with Spec in OKR.deliverables",
        "severity": "error",
    },
    {
        "id": "CS-02",
        "description": "设计→开发一致性：所有代码模块必须有对应 Spec",
        "check": "for each CodeModule: exists Spec referencing CodeModule",
        "severity": "warning",
    },
    {
        "id": "CS-03",
        "description": "开发→部署一致性：所有部署的服务必须有对应 CI 流水线",
        "check": "for each DeploymentConfig: exists CI_Pipeline for the service",
        "severity": "warning",
    },
    {
        "id": "CS-04",
        "description": "部署→运行一致性：所有运行服务必须有告警规则",
        "check": "for each Environment: all services have AlertRules",
        "severity": "error",
    },
    {
        "id": "CS-05",
        "description": "运行→运维一致性：所有事件必须有运行手册",
        "check": "for each Incident: exists Runbook covering the incident type",
        "severity": "error",
    },
]
