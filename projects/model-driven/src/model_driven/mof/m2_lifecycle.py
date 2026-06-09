"""
model_driven.mof.m2_lifecycle — M2 元模型扩展 (全生命周期类型)

新增 ~20 个 M2 类型，覆盖 7 个生命周期阶段和价值体系。
每个类型定义遵循现有 M2 标准格式 (M3 父类 + 状态机 + 属性 + 校验规则 + 关系约束)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .m3_extended import LifecycleStage

# ── M2 类型枚举 ──────────────────────────────────────


class M2Type(Enum):
    """M2 扩展类型枚举"""

    # 规划态 (Planning)
    ROADMAP = "roadmap"  # 路线图
    OKR = "okr"  # 目标与关键结果
    INITIATIVE = "initiative"  # 战略举措

    # 设计态 (Design)
    ADR = "adr"  # 架构决策记录
    SPEC_DESIGN = "spec_design"  # 设计规格
    INTERFACE_CONTRACT = "interface_contract"  # 接口契约

    # 开发态 (Development)
    CODE_MODULE = "code_module"  # 代码模块
    TEST_SUITE = "test_suite"  # 测试套件
    CI_PIPELINE = "ci_pipeline"  # CI 流水线

    # 部署态 (Deployment)
    DEPLOYMENT_CONFIG = "deployment_config"  # 部署配置
    RELEASE_PLAN = "release_plan"  # 发布计划
    ENVIRONMENT = "environment"  # 环境定义

    # 运行态 (Runtime)
    RUNBOOK = "runbook"  # 运行手册
    ALERT_RULE = "alert_rule"  # 告警规则
    DASHBOARD_CONFIG = "dashboard_config"  # 仪表板配置

    # 运维态 (Operations)
    INCIDENT = "incident"  # 事件
    CHANGE_REQUEST = "change_request"  # 变更请求
    MIGRATION_PLAN = "migration_plan"  # 迁移计划

    # 运营态 (Business Ops)
    USER_JOURNEY = "user_journey"  # 用户旅程
    VALUE_STREAM = "value_stream"  # 价值流
    FEEDBACK = "feedback"  # 反馈

    # 价值体系 (Value)
    COST_MODEL = "cost_model"  # 成本模型
    BENEFIT_MODEL = "benefit_model"  # 收益模型
    ROI_ANALYSIS = "roi_analysis"  # ROI 分析


# ── M2 类型 Schema 定义 ─────────────────────────────


@dataclass
class M2Schema:
    """M2 类型 Schema 定义"""

    m2_type: str
    m3_parent: str
    description: str
    icon: str = ""
    lifecycle_stage: LifecycleStage | None = None
    state_machine: dict[str, Any] = field(default_factory=dict)
    required_properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    optional_properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    validation_rules: list[dict[str, Any]] = field(default_factory=list)
    relation_constraints: dict[str, list[str]] = field(default_factory=dict)
    examples: list[dict[str, Any]] = field(default_factory=list)


# ── 规划态类型 ──────────────────────────────────────

M2_ROADMAP = M2Schema(
    m2_type="roadmap",
    m3_parent="DescriptiveElement.Model",
    description="路线图 — 系统或项目的时间线规划。回答'什么时候做什么'。",
    icon="🗺️",
    lifecycle_stage=LifecycleStage.PLANNING,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "生效中", "transitions": ["completed", "cancelled", "archived"]},
        "completed": {"description": "已完成", "transitions": ["archived"]},
        "cancelled": {"description": "已取消", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "timeline": {"type": "list", "description": "时间线 [{milestone, target_date, deliverables}]"},
        "owner": {"type": "string", "description": "负责人"},
    },
    optional_properties={
        "parent_roadmap": {"type": "ref", "description": "父路线图"},
        "dependencies": {"type": "list", "description": "依赖的其他路线图"},
        "progress": {"type": "float", "description": "整体进度 0.0-1.0", "min": 0, "max": 1},
    },
    validation_rules=[
        {"rule": "timeline.size >= 1", "level": "error", "message": "路线图至少需要一个里程碑"},
    ],
    relation_constraints={
        "can_be_source_of": ["References", "DependsOn"],
        "can_be_target_of": ["References", "Realizes"],
    },
)

M2_OKR = M2Schema(
    m2_type="okr",
    m3_parent="ValueElement.Goal",
    description="OKR (目标与关键结果) — 目标对齐工具。回答'我们要达成什么'。",
    icon="🎯",
    lifecycle_stage=LifecycleStage.PLANNING,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "执行中", "transitions": ["completed", "cancelled"]},
        "completed": {"description": "已完成", "transitions": ["archived"]},
        "cancelled": {"description": "已取消", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "objective": {"type": "string", "description": "目标描述 (O)"},
        "key_results": {"type": "list", "description": "关键结果 [{description, target, current, unit}]"},
        "deadline": {"type": "date", "description": "截止日期"},
        "owner": {"type": "string", "description": "负责人"},
    },
    optional_properties={
        "parent_okr": {"type": "ref", "description": "父 OKR"},
        "progress": {"type": "float", "description": "整体进度 0.0-1.0", "min": 0, "max": 1},
        "alignment": {"type": "string", "description": "对齐方向 top-down/bottom-up"},
        "value_tier": {"type": "integer", "description": "价值层级 1-7", "min": 1, "max": 7},
    },
    validation_rules=[
        {"rule": "objective != ''", "level": "error", "message": "OKR 必须有目标描述"},
        {"rule": "key_results.size >= 1", "level": "error", "message": "OKR 至少需要一个关键结果"},
    ],
)

M2_INITIATIVE = M2Schema(
    m2_type="initiative",
    m3_parent="GovernanceElement.Policy",
    description="战略举措 — 为实现战略目标而采取的重大行动。回答'为什么做这个'。",
    icon="🚀",
    lifecycle_stage=LifecycleStage.PLANNING,
    state_machine={
        "proposed": {"description": "提议中", "transitions": ["approved", "rejected"]},
        "approved": {"description": "已批准", "transitions": ["active"]},
        "active": {"description": "执行中", "transitions": ["completed", "cancelled"]},
        "completed": {"description": "已完成", "transitions": ["archived"]},
        "rejected": {"description": "已驳回", "transitions": []},
        "cancelled": {"description": "已取消", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "strategic_goal": {"type": "string", "description": "战略目标"},
        "sponsor": {"type": "string", "description": "发起人"},
        "success_criteria": {"type": "list", "description": "成功标准"},
    },
    optional_properties={
        "linked_okrs": {"type": "list", "description": "关联 OKR ID 列表"},
        "budget": {"type": "float", "description": "预算"},
        "timeline": {"type": "list", "description": "时间线"},
    },
)

# ── 设计态类型 ──────────────────────────────────────

M2_ADR = M2Schema(
    m2_type="adr",
    m3_parent="GovernanceElement.Decision",
    description="ADR (架构决策记录) — 记录重要的架构决策及其背景。回答'为什么这样设计'。",
    icon="📋",
    lifecycle_stage=LifecycleStage.DESIGN,
    state_machine={
        "proposed": {"description": "提议中", "transitions": ["accepted", "rejected", "superseded"]},
        "accepted": {"description": "已采纳", "transitions": ["deprecated", "superseded"]},
        "deprecated": {"description": "已废弃", "transitions": ["superseded"]},
        "superseded": {"description": "被取代", "transitions": ["archived"]},
        "rejected": {"description": "已拒绝", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "context": {"type": "string", "description": "背景和问题陈述"},
        "decision": {"type": "string", "description": "决策内容"},
        "consequences": {"type": "string", "description": "决策后果"},
    },
    optional_properties={
        "alternatives": {"type": "list", "description": "考虑的替代方案"},
        "related_specs": {"type": "list", "description": "关联 Spec ID"},
        "superseded_by": {"type": "ref", "description": "被哪个 ADR 取代"},
    },
    validation_rules=[
        {"rule": "context != ''", "level": "error", "message": "ADR 必须有背景描述"},
        {"rule": "decision != ''", "level": "error", "message": "ADR 必须有决策内容"},
    ],
)

M2_SPEC_DESIGN = M2Schema(
    m2_type="spec_design",
    m3_parent="GovernanceElement.Specification",
    description="设计规格 — 详细的技术设计文档。回答'怎么实现'。",
    icon="📐",
    lifecycle_stage=LifecycleStage.DESIGN,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["review"]},
        "review": {"description": "评审中", "transitions": ["approved", "draft"]},
        "approved": {"description": "已批准", "transitions": ["implementing"]},
        "implementing": {"description": "实现中", "transitions": ["done", "amended"]},
        "done": {"description": "已完成", "transitions": ["archived"]},
        "amended": {"description": "已修订", "transitions": ["review"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "overview": {"type": "string", "description": "概述"},
        "design": {"type": "string", "description": "设计方案"},
        "interfaces": {"type": "list", "description": "接口定义"},
        "author": {"type": "string", "description": "作者"},
    },
    optional_properties={
        "related_adrs": {"type": "list", "description": "关联 ADR ID"},
        "related_okrs": {"type": "list", "description": "关联 OKR ID"},
        "dependencies": {"type": "list", "description": "依赖的其他 Spec"},
        "reviewers": {"type": "list", "description": "评审人"},
    },
)

M2_INTERFACE_CONTRACT = M2Schema(
    m2_type="interface_contract",
    m3_parent="BehavioralElement.Protocol",
    description="接口契约 — 组件间接口的形式化定义。回答'如何交互'。",
    icon="🔗",
    lifecycle_stage=LifecycleStage.DESIGN,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "provider": {"type": "string", "description": "提供方组件"},
        "consumer": {"type": "string", "description": "消费方组件"},
        "schema": {"type": "map", "description": "接口 Schema 定义"},
    },
    optional_properties={
        "version": {"type": "semver", "description": "接口版本"},
        "sla": {"type": "map", "description": "SLA 定义"},
        "protocol": {"type": "string", "description": "通信协议 (MCP/HTTP/gRPC)"},
    },
)

# ── 开发态类型 ──────────────────────────────────────

M2_CODE_MODULE = M2Schema(
    m2_type="code_module",
    m3_parent="StructuralElement.Artifact",
    description="代码模块 — 可独立构建/测试的代码单元。回答'代码在哪'。",
    icon="💻",
    lifecycle_stage=LifecycleStage.DEVELOPMENT,
    state_machine={
        "active": {"description": "活跃", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "path": {"type": "path", "description": "代码路径"},
        "language": {"type": "string", "description": "编程语言"},
        "owner": {"type": "string", "description": "负责人/团队"},
    },
    optional_properties={
        "test_coverage": {"type": "float", "description": "测试覆盖率"},
        "dependencies": {"type": "list", "description": "依赖模块"},
        "build_command": {"type": "string", "description": "构建命令"},
    },
)

M2_TEST_SUITE = M2Schema(
    m2_type="test_suite",
    m3_parent="StructuralElement.Artifact",
    description="测试套件 — 自动化测试集合。回答'如何验证正确性'。",
    icon="🧪",
    lifecycle_stage=LifecycleStage.DEVELOPMENT,
    state_machine={
        "active": {"description": "活跃", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "path": {"type": "path", "description": "测试路径"},
        "test_count": {"type": "integer", "description": "测试用例数"},
        "framework": {"type": "string", "description": "测试框架"},
    },
    optional_properties={
        "pass_rate": {"type": "float", "description": "通过率"},
        "covered_modules": {"type": "list", "description": "覆盖的模块"},
        "ci_integration": {"type": "string", "description": "CI 集成方式"},
    },
)

M2_CI_PIPELINE = M2Schema(
    m2_type="ci_pipeline",
    m3_parent="BehavioralElement.Mechanism",
    description="CI 流水线 — 持续集成自动化流程。回答'如何自动化构建和测试'。",
    icon="⚙️",
    lifecycle_stage=LifecycleStage.DEVELOPMENT,
    state_machine={
        "active": {"description": "运行中", "transitions": ["degraded", "stopped"]},
        "degraded": {"description": "降级", "transitions": ["active", "stopped"]},
        "stopped": {"description": "已停止", "transitions": ["active", "archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "config_path": {"type": "path", "description": "CI 配置文件路径"},
        "stages": {"type": "list", "description": "流水线阶段"},
        "provider": {"type": "string", "description": "CI 提供商 (GitHub Actions/Jenkins/...)"},
    },
)

# ── 部署态类型 ──────────────────────────────────────

M2_DEPLOYMENT_CONFIG = M2Schema(
    m2_type="deployment_config",
    m3_parent="StructuralElement.Artifact",
    description="部署配置 — 服务部署的环境和参数配置。回答'如何部署'。",
    icon="🚢",
    lifecycle_stage=LifecycleStage.DEPLOYMENT,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "target_environment": {"type": "string", "description": "目标环境"},
        "config_path": {"type": "path", "description": "配置文件路径"},
        "strategy": {
            "type": "enum",
            "description": "部署策略",
            "values": ["rolling", "blue_green", "canary", "recreate"],
        },
    },
    optional_properties={
        "health_check": {"type": "map", "description": "健康检查配置"},
        "resources": {"type": "map", "description": "资源配置 (cpu/memory/disk)"},
        "rollback_config": {"type": "map", "description": "回滚配置"},
    },
)

M2_RELEASE_PLAN = M2Schema(
    m2_type="release_plan",
    m3_parent="DescriptiveElement.Model",
    description="发布计划 — 版本发布的详细计划。回答'何时发布什么'。",
    icon="📦",
    lifecycle_stage=LifecycleStage.DEPLOYMENT,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["approved"]},
        "approved": {"description": "已批准", "transitions": ["in_progress"]},
        "in_progress": {"description": "执行中", "transitions": ["completed", "rolled_back"]},
        "completed": {"description": "已完成", "transitions": ["archived"]},
        "rolled_back": {"description": "已回滚", "transitions": ["draft"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "version": {"type": "semver", "description": "发布版本号"},
        "release_date": {"type": "date", "description": "发布日期"},
        "changes": {"type": "list", "description": "变更列表"},
    },
    optional_properties={
        "rollback_plan": {"type": "string", "description": "回滚计划"},
        "approval_chain": {"type": "list", "description": "审批链"},
        "hardening_stage": {
            "type": "enum",
            "description": "代码硬化阶段 — 从可变到不可变的渐进式固化 (预留接口，当前未完全实现)",
            "values": ["none", "canary", "blue_green", "full", "hardened"],
        },
        "hardening_verified_runs": {
            "type": "integer",
            "description": "硬化前已验证的运行次数 (达到阈值后自动进入 hardened 状态)",
        },
    },
)

M2_ENVIRONMENT = M2Schema(
    m2_type="environment",
    m3_parent="StructuralElement.Component",
    description="环境 — 部署运行的系统环境。回答'运行在哪'。",
    icon="🌍",
    lifecycle_stage=LifecycleStage.DEPLOYMENT,
    state_machine={
        "active": {"description": "活跃", "transitions": ["degraded", "stopped"]},
        "degraded": {"description": "降级", "transitions": ["active", "stopped"]},
        "stopped": {"description": "已停止", "transitions": ["active", "archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "env_type": {"type": "enum", "description": "环境类型", "values": ["dev", "staging", "production", "sandbox"]},
        "host": {"type": "string", "description": "主机地址"},
    },
    optional_properties={
        "services": {"type": "list", "description": "部署的服务列表"},
        "config_vars": {"type": "map", "description": "环境变量"},
    },
)

# ── 运行态类型 ──────────────────────────────────────

M2_RUNBOOK = M2Schema(
    m2_type="runbook",
    m3_parent="GovernanceElement.Specification",
    description="运行手册 — 系统运行操作指南。回答'如何操作和维护'。",
    icon="📖",
    lifecycle_stage=LifecycleStage.RUNTIME,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "procedures": {"type": "list", "description": "操作流程 [{name, steps, expected_outcome}]"},
        "owner": {"type": "string", "description": "负责人"},
    },
    optional_properties={
        "related_alerts": {"type": "list", "description": "关联告警规则"},
        "escalation": {"type": "map", "description": "升级策略"},
    },
)

M2_ALERT_RULE = M2Schema(
    m2_type="alert_rule",
    m3_parent="GovernanceElement.Constraint",
    description="告警规则 — 监控告警的条件和动作。回答'何时告警'。",
    icon="🚨",
    lifecycle_stage=LifecycleStage.RUNTIME,
    state_machine={
        "active": {"description": "生效中", "transitions": ["silenced", "deprecated"]},
        "silenced": {"description": "静默中", "transitions": ["active", "deprecated"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "metric": {"type": "string", "description": "监控指标"},
        "condition": {"type": "string", "description": "触发条件 (如 > 80% )"},
        "severity": {"type": "enum", "description": "严重度", "values": ["critical", "high", "medium", "low"]},
    },
    optional_properties={
        "notification_channel": {"type": "string", "description": "通知渠道"},
        "runbook_ref": {"type": "ref", "description": "关联运行手册"},
        "cooldown_minutes": {"type": "integer", "description": "冷却时间(分钟)"},
    },
)

M2_DASHBOARD_CONFIG = M2Schema(
    m2_type="dashboard_config",
    m3_parent="DescriptiveElement.View",
    description="仪表板配置 — 可观测性仪表板定义。回答'如何可视化监控'。",
    icon="📊",
    lifecycle_stage=LifecycleStage.RUNTIME,
    state_machine={
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "panels": {"type": "list", "description": "面板配置 [{title, metric, type, position}]"},
        "refresh_interval": {"type": "integer", "description": "刷新间隔(秒)"},
    },
)

# ── 运维态类型 ──────────────────────────────────────

M2_INCIDENT = M2Schema(
    m2_type="incident",
    m3_parent="BehavioralElement.Process",
    description="事件 — 系统故障或异常事件。回答'出了什么问题'。",
    icon="🔥",
    lifecycle_stage=LifecycleStage.OPERATIONS,
    state_machine={
        "detected": {"description": "已检测", "transitions": ["investigating"]},
        "investigating": {"description": "调查中", "transitions": ["mitigating", "resolved"]},
        "mitigating": {"description": "缓解中", "transitions": ["resolved", "escalated"]},
        "resolved": {"description": "已解决", "transitions": ["reviewed"]},
        "escalated": {"description": "已升级", "transitions": ["mitigating", "resolved"]},
        "reviewed": {"description": "已复盘", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "severity": {"type": "enum", "description": "严重度", "values": ["P0", "P1", "P2", "P3"]},
        "description": {"type": "string", "description": "事件描述"},
        "detected_at": {"type": "datetime", "description": "检测时间"},
    },
    optional_properties={
        "affected_services": {"type": "list", "description": "受影响的服务"},
        "root_cause": {"type": "string", "description": "根因分析"},
        "resolution": {"type": "string", "description": "解决方案"},
        "postmortem": {"type": "string", "description": "事后复盘"},
    },
)

M2_CHANGE_REQUEST = M2Schema(
    m2_type="change_request",
    m3_parent="GovernanceElement.Policy",
    description="变更请求 — 系统变更的审批和执行记录。回答'改了什么'。",
    icon="🔧",
    lifecycle_stage=LifecycleStage.OPERATIONS,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["submitted"]},
        "submitted": {"description": "已提交", "transitions": ["approved", "rejected"]},
        "approved": {"description": "已批准", "transitions": ["in_progress"]},
        "in_progress": {"description": "执行中", "transitions": ["completed", "failed"]},
        "completed": {"description": "已完成", "transitions": ["verified"]},
        "verified": {"description": "已验证", "transitions": ["archived"]},
        "failed": {"description": "失败", "transitions": ["draft"]},
        "rejected": {"description": "已驳回", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "change_type": {
            "type": "enum",
            "description": "变更类型",
            "values": ["config", "code", "infrastructure", "data"],
        },
        "description": {"type": "string", "description": "变更描述"},
        "risk_level": {"type": "enum", "description": "风险等级", "values": ["low", "medium", "high", "critical"]},
    },
)

M2_MIGRATION_PLAN = M2Schema(
    m2_type="migration_plan",
    m3_parent="DescriptiveElement.Model",
    description="迁移计划 — 系统/数据迁移的详细方案。回答'如何迁移'。",
    icon="🚚",
    lifecycle_stage=LifecycleStage.OPERATIONS,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["approved"]},
        "approved": {"description": "已批准", "transitions": ["in_progress"]},
        "in_progress": {"description": "执行中", "transitions": ["completed", "rolled_back"]},
        "completed": {"description": "已完成", "transitions": ["verified"]},
        "verified": {"description": "已验证", "transitions": ["archived"]},
        "rolled_back": {"description": "已回滚", "transitions": ["draft"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "source": {"type": "string", "description": "迁移源"},
        "target": {"type": "string", "description": "迁移目标"},
        "steps": {"type": "list", "description": "迁移步骤"},
    },
    optional_properties={
        "rollback_plan": {"type": "string", "description": "回滚计划"},
        "downtime_estimate": {"type": "string", "description": "预估停机时间"},
    },
)

# ── 运营态类型 ──────────────────────────────────────

M2_USER_JOURNEY = M2Schema(
    m2_type="user_journey",
    m3_parent="DescriptiveElement.Model",
    description="用户旅程 — 用户使用系统的完整路径。回答'用户如何使用'。",
    icon="👤",
    lifecycle_stage=LifecycleStage.BUSINESS_OPS,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "persona": {"type": "string", "description": "用户画像"},
        "steps": {"type": "list", "description": "旅程步骤 [{step, action, touchpoint, emotion}]"},
        "goal": {"type": "string", "description": "用户目标"},
    },
    optional_properties={
        "pain_points": {"type": "list", "description": "痛点"},
        "opportunities": {"type": "list", "description": "改进机会"},
        "metrics": {"type": "map", "description": "相关指标"},
    },
)

M2_VALUE_STREAM = M2Schema(
    m2_type="value_stream",
    m3_parent="DescriptiveElement.Model",
    description="价值流 — 从需求到交付的完整价值链路。回答'价值如何流动'。",
    icon="💎",
    lifecycle_stage=LifecycleStage.BUSINESS_OPS,
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "stages": {"type": "list", "description": "价值流阶段"},
        "lead_time": {"type": "float", "description": "前置时间(天)"},
        "cycle_time": {"type": "float", "description": "周期时间(天)"},
    },
    optional_properties={
        "bottlenecks": {"type": "list", "description": "瓶颈"},
        "waste": {"type": "list", "description": "浪费点"},
    },
)

M2_FEEDBACK = M2Schema(
    m2_type="feedback",
    m3_parent="StructuralElement.Entity",
    description="反馈 — 用户或系统的反馈信息。回答'用户怎么说'。",
    icon="💬",
    lifecycle_stage=LifecycleStage.BUSINESS_OPS,
    state_machine={
        "collected": {"description": "已收集", "transitions": ["analyzing"]},
        "analyzing": {"description": "分析中", "transitions": ["actioned", "dismissed"]},
        "actioned": {"description": "已处理", "transitions": ["verified"]},
        "verified": {"description": "已验证", "transitions": ["archived"]},
        "dismissed": {"description": "已忽略", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "source": {"type": "string", "description": "反馈来源"},
        "content": {"type": "string", "description": "反馈内容"},
        "sentiment": {"type": "enum", "description": "情感倾向", "values": ["positive", "neutral", "negative"]},
    },
    optional_properties={
        "priority": {"type": "enum", "description": "优先级", "values": ["P0", "P1", "P2", "P3"]},
        "related_feature": {"type": "string", "description": "关联功能"},
    },
)

# ── 价值体系类型 ────────────────────────────────────

M2_COST_MODEL = M2Schema(
    m2_type="cost_model",
    m3_parent="ValueElement.CostModel",
    description="成本模型 — 系统运行的成本归因和分析。回答'花了多少钱'。",
    icon="💰",
    state_machine={
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "resource_type": {
            "type": "enum",
            "description": "资源类型",
            "values": ["compute", "storage", "human", "api", "license"],
        },
        "unit_cost": {"type": "float", "description": "单位成本"},
        "period": {"type": "enum", "description": "计费周期", "values": ["hourly", "daily", "monthly", "yearly"]},
    },
    optional_properties={
        "attribution_target": {"type": "ref", "description": "成本归因目标"},
        "estimated_annual_cost": {"type": "float", "description": "预估年成本"},
        "actual_cost_ytd": {"type": "float", "description": "年度实际成本"},
    },
)

M2_BENEFIT_MODEL = M2Schema(
    m2_type="benefit_model",
    m3_parent="ValueElement.BenefitModel",
    description="收益模型 — 系统产生的价值量化。回答'创造了多少价值'。",
    icon="📈",
    state_machine={
        "active": {"description": "生效中", "transitions": ["deprecated", "archived"]},
        "deprecated": {"description": "已废弃", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "benefit_type": {
            "type": "enum",
            "description": "收益类型",
            "values": ["revenue", "cost_saving", "efficiency", "user_satisfaction", "quality"],
        },
        "estimated_value": {"type": "float", "description": "预估价值"},
        "measurement_method": {"type": "string", "description": "度量方法"},
    },
    optional_properties={
        "attribution_target": {"type": "ref", "description": "收益归因目标"},
        "actual_value": {"type": "float", "description": "实际价值"},
        "roi": {"type": "float", "description": "ROI 比率"},
    },
)

M2_ROI_ANALYSIS = M2Schema(
    m2_type="roi_analysis",
    m3_parent="DescriptiveElement.Model",
    description="ROI 分析 — 投入产出比分析。回答'值不值得做'。",
    icon="🎯",
    state_machine={
        "draft": {"description": "草稿", "transitions": ["active"]},
        "active": {"description": "生效中", "transitions": ["archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "investment": {"type": "float", "description": "投入"},
        "returns": {"type": "float", "description": "回报"},
        "timeframe": {"type": "string", "description": "时间范围"},
    },
    optional_properties={
        "payback_period": {"type": "float", "description": "回收期(月)"},
        "npv": {"type": "float", "description": "净现值"},
        "risk_adjustment": {"type": "float", "description": "风险调整系数"},
    },
)


# ── 运维态类型: Trigger (异步触发机制) ─────────────

M2_TRIGGER = M2Schema(
    m2_type="trigger",
    m3_parent="BehavioralElement.Mechanism",
    description="异步触发机制 — 统一管理 git hooks/cron/daemon/watchdog/event bus 等触发机制。回答'什么触发什么'。",
    icon="🔌",
    lifecycle_stage=LifecycleStage.OPERATIONS,
    state_machine={
        "defined": {"description": "已定义·待激活", "transitions": ["active"]},
        "active": {"description": "运行中", "transitions": ["degraded", "stopped"]},
        "degraded": {"description": "降级运行", "transitions": ["active", "stopped"]},
        "stopped": {"description": "已停止", "transitions": ["active", "archived"]},
        "archived": {"description": "已归档", "transitions": []},
    },
    required_properties={
        "trigger_type": {
            "type": "enum",
            "description": "触发机制类型",
            "values": [
                "git_hook",
                "cron",
                "daemon",
                "watchdog",
                "event_bus",
                "sse",
                "file_watch",
                "bus_consumer",
                "launchd",
                "scheduler",
            ],
        },
        "trigger_source": {
            "type": "string",
            "description": "触发源 (git commit / cron schedule / file change / http request)",
        },
        "trigger_action": {"type": "string", "description": "触发后执行的动作"},
        "schedule": {
            "type": "string",
            "description": "调度策略 (cron表达式 / on_push / on_file_change / every Ns / continuous)",
        },
    },
    optional_properties={
        "interval_seconds": {"type": "integer", "description": "间隔秒数"},
        "dependencies": {"type": "list", "description": "依赖的其他 trigger ID 列表"},
        "health_check": {"type": "map", "description": "{endpoint, expected_status, timeout}"},
        "retry_policy": {"type": "map", "description": "{max_retries, backoff_strategy}"},
        "gate_checks": {"type": "list", "description": "触发前门禁检查项"},
    },
    validation_rules=[
        {
            "rule": "trigger_type in ['git_hook','cron','daemon','watchdog','event_bus','sse','file_watch','bus_consumer','launchd','scheduler']",
            "level": "error",
            "message": "trigger_type 必须是已知类型",
        },
        {"rule": "trigger_source != ''", "level": "error", "message": "必须声明触发源"},
    ],
    relation_constraints={
        "can_be_source_of": ["DependsOn", "Triggers"],
        "can_be_target_of": ["Constrains", "Audits"],
    },
)


# ── 全量 M2 Schema 注册表 ──────────────────────────


ALL_M2_SCHEMAS: dict[str, M2Schema] = {
    # 规划态
    "roadmap": M2_ROADMAP,
    "okr": M2_OKR,
    "initiative": M2_INITIATIVE,
    # 设计态
    "adr": M2_ADR,
    "spec_design": M2_SPEC_DESIGN,
    "interface_contract": M2_INTERFACE_CONTRACT,
    # 开发态
    "code_module": M2_CODE_MODULE,
    "test_suite": M2_TEST_SUITE,
    "ci_pipeline": M2_CI_PIPELINE,
    # 部署态
    "deployment_config": M2_DEPLOYMENT_CONFIG,
    "release_plan": M2_RELEASE_PLAN,
    "environment": M2_ENVIRONMENT,
    # 运行态
    "runbook": M2_RUNBOOK,
    "alert_rule": M2_ALERT_RULE,
    "dashboard_config": M2_DASHBOARD_CONFIG,
    # 运维态
    "incident": M2_INCIDENT,
    "change_request": M2_CHANGE_REQUEST,
    "migration_plan": M2_MIGRATION_PLAN,
    # 运营态
    "user_journey": M2_USER_JOURNEY,
    "value_stream": M2_VALUE_STREAM,
    "feedback": M2_FEEDBACK,
    # 价值体系
    "cost_model": M2_COST_MODEL,
    "benefit_model": M2_BENEFIT_MODEL,
    "roi_analysis": M2_ROI_ANALYSIS,
    # 触发机制
    "trigger": M2_TRIGGER,
}


def get_schema(m2_type: str) -> M2Schema | None:
    """获取 M2 类型 Schema"""
    return ALL_M2_SCHEMAS.get(m2_type)


def list_schemas_by_stage(stage: LifecycleStage) -> list[M2Schema]:
    """按生命周期阶段列出 M2 类型"""
    return [s for s in ALL_M2_SCHEMAS.values() if s.lifecycle_stage == stage]


def list_all_schema_names() -> list[str]:
    """列出所有 M2 类型名称"""
    return list(ALL_M2_SCHEMAS.keys())
