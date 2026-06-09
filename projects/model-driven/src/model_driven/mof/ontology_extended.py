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

# ── Trigger 本体论映射 ──────────────────────────────

# Trigger 等价映射: 概念等价
TRIGGER_EQUIVALENCES = [
    {"a": "git_hook", "b": "Git Hook", "relation": "EquivalentTo", "note": "触发类型与实现概念等价"},
    {"a": "cron", "b": "定时任务调度", "relation": "EquivalentTo", "note": "触发类型与实现概念等价"},
    {"a": "daemon", "b": "守护进程", "relation": "EquivalentTo", "note": "触发类型与实现概念等价"},
    {"a": "watchdog", "b": "健康监控", "relation": "EquivalentTo", "note": "触发类型与实现概念等价"},
    {"a": "event_bus", "b": "事件总线", "relation": "EquivalentTo", "note": "触发类型与实现概念等价"},
    {"a": "launchd", "b": "系统服务管理", "relation": "EquivalentTo", "note": "触发类型与实现概念等价"},
    {"a": "TriggerM0Manager", "b": "M0 运行时快照", "relation": "EquivalentTo", "note": "Trigger 的 M0 层实现"},
]

# Trigger 依赖关系: 运行时依赖拓扑
TRIGGER_DEPENDENCIES = [
    {
        "dependent": "TRIGGER-ECOS-DAEMON",
        "depends_on": "TRIGGER-AGORA-EVENTBUS",
        "note": "daemon 自反验证依赖 EventBus 可用",
    },
    {
        "dependent": "TRIGGER-CRON-SERVICE",
        "depends_on": "TRIGGER-AGORA-LAUNCHD",
        "note": "Cron Service 依赖 Agora MCP Hub",
    },
    {"dependent": "TRIGGER-SCHEDULER", "depends_on": "TRIGGER-OMO-DAEMON", "note": "Scheduler 依赖 OMO 治理守护进程"},
    {"dependent": "TRIGGER-AGORA-WATCHDOG", "depends_on": "TRIGGER-AGORA-LAUNCHD", "note": "Watchdog 监控 Agora 自身"},
]

# Trigger 泛化层次: M3 继承
TRIGGER_GENERALIZATIONS = [
    {"child": "trigger", "parent": "Mechanism", "note": "Trigger 是 Mechanism 的子类型 (M3→M2)"},
    {"child": "TriggerRuntimeSnapshot", "parent": "M0_Snapshot", "note": "M0 快照是 M0 层的实例"},
]

# Trigger 推导规则 (本体论层, 供 DerivationEngine 执行)
TRIGGER_DERIVATION_RULES = [
    {
        "id": "DR-TRIGGER-01",
        "description": "Cron 任务超时未执行 → 调度器健康风险",
        "rule": "if (Trigger.schedule matches cron) and (last_execution > expected_next) then Trigger.risk += 'overdue'",
        "priority": "high",
    },
    {
        "id": "DR-TRIGGER-02",
        "description": "Watchdog 连续失败超过阈值 → 服务不可用风险",
        "rule": "if (Trigger.type == 'watchdog') and (consecutive_failures >= 3) then Service.risk += 'unavailable'",
        "priority": "critical",
    },
    {
        "id": "DR-TRIGGER-03",
        "description": "Git Hook 触发但 MOF 萃取失败 → 知识丢失风险",
        "rule": "if (Trigger.type == 'git_hook') and (post_commit.extraction_failed) then Knowledge.risk += 'loss'",
        "priority": "high",
    },
    {
        "id": "DR-TRIGGER-04",
        "description": "EventBus 事件积压超过阈值 → 事件处理延迟风险",
        "rule": "if (Trigger.type == 'event_bus') and (event_queue_size > 1000) then EventBus.risk += 'backlog'",
        "priority": "high",
    },
    {
        "id": "DR-TRIGGER-05",
        "description": "Daemon 周期超过预期 2 倍 → 守护进程卡死风险",
        "rule": "if (Trigger.type == 'daemon') and (last_cycle_duration > 2 * expected_interval) then Daemon.risk += 'stuck'",
        "priority": "critical",
    },
    {
        "id": "DR-TRIGGER-DEP",
        "description": "Trigger 依赖不满足 → 级联风险",
        "rule": "for each Trigger.dependencies: if dep.status != 'healthy' then Trigger.risk += 'dependency_unhealthy'",
        "priority": "high",
    },
]
