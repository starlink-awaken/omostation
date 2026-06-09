"""
model_driven.mof.m3_extended — M3 元元模型扩展

在现有 M3 (16 Element 类型 + 12 Relation 类型) 基础上新增：
- 生命周期元素 (LifecycleElement): Stage, Gate
- 价值元素 (ValueElement): Goal, CostModel, BenefitModel
- 新增关系: TransitionsTo, DependsOnPhase, AttributesValue

这些扩展使 MOF 能够覆盖系统全生命周期建模。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ── 生命周期阶段枚举 ──────────────────────────────────


class LifecycleStage(Enum):
    """7 个标准生命周期阶段"""

    PLANNING = "planning"  # 规划态
    DESIGN = "design"  # 设计态
    DEVELOPMENT = "development"  # 开发态
    DEPLOYMENT = "deployment"  # 部署态
    RUNTIME = "runtime"  # 运行态
    OPERATIONS = "operations"  # 运维态
    BUSINESS_OPS = "business_ops"  # 运营态

    @classmethod
    def order(cls, stage: LifecycleStage) -> int:
        """返回阶段序号 (0-6)"""
        return list(cls).index(stage)

    @classmethod
    def from_str(cls, s: str) -> LifecycleStage:
        mapping = {e.value: e for e in cls}
        if s.lower() not in mapping:
            raise ValueError(f"未知生命周期阶段: {s}, 有效值: {list(mapping.keys())}")
        return mapping[s.lower()]


# ── M3 扩展元素类型 ──────────────────────────────────


class M3ElementType(Enum):
    """M3 扩展元素类型 — 新增生命周期和价值大类"""

    # 原有 4 大类 (16 类型) 已在 ecos/m3.yaml 中定义
    # 这里仅定义新增类型

    # ── 生命周期元素 (第 5 大类) ──
    LIFECYCLE_ELEMENT = "LifecycleElement"  # 抽象根
    STAGE = "Stage"  # 阶段
    GATE = "Gate"  # 门禁
    TRANSITION = "Transition"  # 转换

    # ── 价值元素 (第 6 大类) ──
    VALUE_ELEMENT = "ValueElement"  # 抽象根
    GOAL = "Goal"  # 目标 (OKR)
    KEY_RESULT = "KeyResult"  # 关键结果
    COST_MODEL = "CostModel"  # 成本模型
    BENEFIT_MODEL = "BenefitModel"  # 收益模型


class M3RelationType(Enum):
    """M3 扩展关系类型"""

    # 生命周期关系
    TRANSITIONS_TO = "TransitionsTo"  # 阶段 A → 阶段 B
    GATES = "Gates"  # 门禁 G 控制 阶段 S
    BELONGS_TO_STAGE = "BelongsToStage"  # 元素属于某阶段

    # 价值关系
    ATTRIBUTES_VALUE = "AttributesValue"  # 价值归因
    MEASURED_BY = "MeasuredBy"  # 目标由 KR 衡量
    INCURS_COST = "IncursCost"  # 产生成本


# ── 核心数据类 ──────────────────────────────────────


@dataclass
class Stage:
    """生命周期阶段定义"""

    id: str
    name: str
    stage: LifecycleStage
    order: int
    description: str = ""
    entry_criteria: list[str] = field(default_factory=list)
    exit_criteria: list[str] = field(default_factory=list)
    core_activities: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    stakeholders: list[str] = field(default_factory=list)
    parent_stage: str | None = None  # 父阶段 ID (子阶段)
    duration_target_days: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Gate:
    """阶段间门禁检查点"""

    id: str
    name: str
    from_stage: LifecycleStage
    to_stage: LifecycleStage
    checks: list[dict[str, Any]] = field(default_factory=list)
    auto_pass: bool = False
    required_approvals: list[str] = field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Transition:
    """阶段转换记录"""

    id: str
    from_stage: LifecycleStage
    to_stage: LifecycleStage
    triggered_by: str = ""  # 触发者/触发条件
    gate_id: str | None = None  # 通过的门禁 ID
    timestamp: str = ""
    status: str = "pending"  # pending/approved/rejected/completed
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Goal:
    """OKR 目标"""

    id: str
    name: str
    description: str = ""
    objective: str = ""  # O: 目标描述
    key_results: list[KeyResult] = field(default_factory=list)
    progress: float = 0.0  # 0.0 - 1.0
    deadline: str = ""
    owner: str = ""
    parent_goal_id: str | None = None
    status: str = "active"  # draft/active/completed/cancelled
    value_tier: int = 0  # 1-7
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KeyResult:
    """OKR 关键结果"""

    id: str
    description: str
    target_value: float = 100.0
    current_value: float = 0.0
    unit: str = "%"
    weight: float = 1.0  # 权重
    status: str = "active"  # active/completed/cancelled
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        if self.target_value == 0:
            return 1.0
        return min(self.current_value / self.target_value, 1.0)


@dataclass
class CostModel:
    """成本模型"""

    id: str
    name: str
    resource_type: str = ""  # compute/storage/human/api/license
    unit_cost: float = 0.0
    unit: str = ""  # 元/小时, 元/GB, etc.
    attribution_target: str = ""  # 成本归因目标 ID
    period: str = "monthly"  # hourly/daily/monthly/yearly
    estimated_annual_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenefitModel:
    """收益模型"""

    id: str
    name: str
    benefit_type: str = ""  # revenue/cost_saving/efficiency/user_satisfaction
    estimated_value: float = 0.0
    unit: str = ""  # 元, 小时, 用户数
    attribution_target: str = ""
    measurement_method: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ── 7 阶段标准定义 ──────────────────────────────────


STANDARD_STAGES: dict[LifecycleStage, Stage] = {
    LifecycleStage.PLANNING: Stage(
        id="STAGE-PLANNING",
        name="规划态",
        stage=LifecycleStage.PLANNING,
        order=0,
        description="目标设定、需求分析、路线图规划",
        entry_criteria=["OKR 已起草", "需求已收集"],
        exit_criteria=["OKR 已审批", "Spec 已起草", "ADR 已记录关键决策"],
        core_activities=["OKR 制定", "需求分析", "技术选型", "路线图规划"],
        deliverables=["OKR 文档", "需求文档", "技术选型报告", "路线图"],
        stakeholders=["产品负责人", "架构师", "技术负责人"],
        duration_target_days=14,
    ),
    LifecycleStage.DESIGN: Stage(
        id="STAGE-DESIGN",
        name="设计态",
        stage=LifecycleStage.DESIGN,
        order=1,
        description="架构设计、接口定义、ADR 记录",
        entry_criteria=["Spec 已起草", "关键 ADR 已记录"],
        exit_criteria=["Spec 已审批", "接口契约已定义", "设计评审通过"],
        core_activities=["架构设计", "接口定义", "ADR 记录", "设计评审"],
        deliverables=["设计文档", "接口契约", "ADR 记录", "设计评审报告"],
        stakeholders=["架构师", "技术负责人", "开发团队"],
        duration_target_days=7,
    ),
    LifecycleStage.DEVELOPMENT: Stage(
        id="STAGE-DEVELOPMENT",
        name="开发态",
        stage=LifecycleStage.DEVELOPMENT,
        order=2,
        description="编码实现、测试、CI 集成",
        entry_criteria=["Spec 已审批", "接口契约已定义"],
        exit_criteria=["测试通过", "CI 绿灯", "Code Review 通过"],
        core_activities=["编码实现", "单元测试", "集成测试", "Code Review"],
        deliverables=["代码", "测试套件", "CI 配置"],
        stakeholders=["开发团队", "QA"],
        duration_target_days=14,
    ),
    LifecycleStage.DEPLOYMENT: Stage(
        id="STAGE-DEPLOYMENT",
        name="部署态",
        stage=LifecycleStage.DEPLOYMENT,
        order=3,
        description="发布部署、环境配置、冒烟测试",
        entry_criteria=["测试通过", "CI 绿灯"],
        exit_criteria=["部署成功", "冒烟测试通过", "监控已配置"],
        core_activities=["发布部署", "环境配置", "冒烟测试", "监控配置"],
        deliverables=["部署包", "环境配置", "冒烟测试报告"],
        stakeholders=["DevOps", "SRE"],
        duration_target_days=2,
    ),
    LifecycleStage.RUNTIME: Stage(
        id="STAGE-RUNTIME",
        name="运行态",
        stage=LifecycleStage.RUNTIME,
        order=4,
        description="系统运行、健康监控、性能观测",
        entry_criteria=["部署成功", "监控已配置"],
        exit_criteria=["运行稳定 (SLA 达标)", "无严重告警"],
        core_activities=["健康监控", "性能观测", "日志分析", "告警响应"],
        deliverables=["健康报告", "性能报告", "SLA 报告"],
        stakeholders=["SRE", "运维团队"],
        duration_target_days=0,  # 持续运行
    ),
    LifecycleStage.OPERATIONS: Stage(
        id="STAGE-OPERATIONS",
        name="运维态",
        stage=LifecycleStage.OPERATIONS,
        order=5,
        description="故障修复、变更管理、迁移升级",
        entry_criteria=["告警触发 或 维护窗口"],
        exit_criteria=["问题已解决", "变更已完成"],
        core_activities=["故障排查", "变更管理", "迁移升级", "回滚"],
        deliverables=["故障报告", "变更记录", "迁移报告"],
        stakeholders=["SRE", "运维团队", "开发团队"],
        duration_target_days=3,
    ),
    LifecycleStage.BUSINESS_OPS: Stage(
        id="STAGE-BUSINESS_OPS",
        name="运营态",
        stage=LifecycleStage.BUSINESS_OPS,
        order=6,
        description="价值评估、用户反馈、持续优化",
        entry_criteria=["系统已上线运行"],
        exit_criteria=["价值目标已评估"],
        core_activities=["价值归因", "用户反馈收集", "ROI 分析", "优化建议"],
        deliverables=["价值报告", "用户反馈报告", "优化建议"],
        stakeholders=["产品负责人", "业务团队"],
        duration_target_days=30,
    ),
}


# ── 标准门禁定义 ──────────────────────────────────


STANDARD_GATES: list[Gate] = [
    Gate(
        id="GATE-PLAN-TO-DESIGN",
        name="规划→设计 门禁",
        from_stage=LifecycleStage.PLANNING,
        to_stage=LifecycleStage.DESIGN,
        checks=[
            {"name": "OKR 审批", "type": "approval", "required": True},
            {"name": "Spec 草案完成", "type": "document", "required": True},
            {"name": "关键 ADR 记录", "type": "document", "required": True},
        ],
        required_approvals=["技术负责人", "产品负责人"],
    ),
    Gate(
        id="GATE-DESIGN-TO-DEV",
        name="设计→开发 门禁",
        from_stage=LifecycleStage.DESIGN,
        to_stage=LifecycleStage.DEVELOPMENT,
        checks=[
            {"name": "Spec 审批", "type": "approval", "required": True},
            {"name": "接口契约定义", "type": "document", "required": True},
            {"name": "设计评审通过", "type": "review", "required": True},
        ],
        required_approvals=["架构师", "技术负责人"],
    ),
    Gate(
        id="GATE-DEV-TO-DEPLOY",
        name="开发→部署 门禁",
        from_stage=LifecycleStage.DEVELOPMENT,
        to_stage=LifecycleStage.DEPLOYMENT,
        checks=[
            {"name": "测试通过率 >= 95%", "type": "metric", "threshold": 95.0},
            {"name": "CI 绿灯", "type": "ci", "required": True},
            {"name": "Code Review 通过", "type": "review", "required": True},
        ],
        required_approvals=["技术负责人"],
    ),
    Gate(
        id="GATE-DEPLOY-TO-RUN",
        name="部署→运行 门禁",
        from_stage=LifecycleStage.DEPLOYMENT,
        to_stage=LifecycleStage.RUNTIME,
        checks=[
            {"name": "部署成功", "type": "deploy", "required": True},
            {"name": "冒烟测试通过", "type": "test", "required": True},
            {"name": "监控已配置", "type": "config", "required": True},
        ],
        auto_pass=True,
    ),
]
