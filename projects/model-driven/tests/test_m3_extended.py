"""
Tests for model_driven.mof.m3_extended — M3 元元模型扩展
"""

import pytest
from model_driven.mof.m3_extended import (
    STANDARD_GATES,
    STANDARD_STAGES,
    BenefitModel,
    CostModel,
    Gate,
    Goal,
    KeyResult,
    LifecycleStage,
    M3ElementType,
    M3RelationType,
    Stage,
    Transition,
)


class TestLifecycleStage:
    def test_enum_values(self):
        assert len(list(LifecycleStage)) == 7
        assert LifecycleStage.PLANNING.value == "planning"
        assert LifecycleStage.DESIGN.value == "design"
        assert LifecycleStage.DEVELOPMENT.value == "development"
        assert LifecycleStage.DEPLOYMENT.value == "deployment"
        assert LifecycleStage.RUNTIME.value == "runtime"
        assert LifecycleStage.OPERATIONS.value == "operations"
        assert LifecycleStage.BUSINESS_OPS.value == "business_ops"

    def test_order(self):
        assert LifecycleStage.order(LifecycleStage.PLANNING) == 0
        assert LifecycleStage.order(LifecycleStage.DESIGN) == 1
        assert LifecycleStage.order(LifecycleStage.BUSINESS_OPS) == 6

    def test_from_str(self):
        assert LifecycleStage.from_str("planning") == LifecycleStage.PLANNING
        assert LifecycleStage.from_str("runtime") == LifecycleStage.RUNTIME
        with pytest.raises(ValueError):
            LifecycleStage.from_str("unknown")


class TestStandardStages:
    def test_all_stages_defined(self):
        assert len(STANDARD_STAGES) == 7
        for stage in LifecycleStage:
            assert stage in STANDARD_STAGES

    def test_stage_properties(self):
        planning = STANDARD_STAGES[LifecycleStage.PLANNING]
        assert planning.name == "规划态"
        assert planning.order == 0
        assert len(planning.entry_criteria) > 0
        assert len(planning.exit_criteria) > 0
        assert len(planning.core_activities) > 0
        assert len(planning.deliverables) > 0

    def test_stage_order_sequential(self):
        stages = sorted(STANDARD_STAGES.values(), key=lambda s: s.order)
        for i in range(len(stages) - 1):
            assert stages[i].order + 1 == stages[i + 1].order


class TestStandardGates:
    def test_gates_count(self):
        assert len(STANDARD_GATES) == 4

    def test_gate_plan_to_design(self):
        gate = STANDARD_GATES[0]
        assert gate.from_stage == LifecycleStage.PLANNING
        assert gate.to_stage == LifecycleStage.DESIGN
        assert len(gate.checks) == 3
        assert len(gate.required_approvals) >= 1

    def test_gate_deploy_to_run_auto_pass(self):
        gate = STANDARD_GATES[3]
        assert gate.from_stage == LifecycleStage.DEPLOYMENT
        assert gate.to_stage == LifecycleStage.RUNTIME
        assert gate.auto_pass is True


class TestGoal:
    def test_create_goal(self):
        kr1 = KeyResult(id="KR-1", description="完成 10 个测试", target_value=10, current_value=5)
        kr2 = KeyResult(id="KR-2", description="覆盖率 80%", target_value=80, current_value=60)
        goal = Goal(
            id="G-1",
            name="提升测试覆盖率",
            objective="将测试覆盖率提升到 80%",
            key_results=[kr1, kr2],
            deadline="2026-07-01",
        )
        assert goal.progress == 0.0
        assert len(goal.key_results) == 2

    def test_key_result_progress(self):
        kr = KeyResult(id="KR-1", description="完成 10 个", target_value=10, current_value=7)
        assert kr.progress == 0.7

        kr2 = KeyResult(id="KR-2", description="完成 10 个", target_value=10, current_value=10)
        assert kr2.progress == 1.0

        kr3 = KeyResult(id="KR-3", description="完成", target_value=0, current_value=0)
        assert kr3.progress == 1.0  # edge case


class TestCostModel:
    def test_create_cost_model(self):
        cm = CostModel(
            id="CM-1",
            name="API 调用成本",
            resource_type="api",
            unit_cost=0.01,
            unit="元/次",
            estimated_annual_cost=10000.0,
        )
        assert cm.resource_type == "api"
        assert cm.unit_cost == 0.01


class TestBenefitModel:
    def test_create_benefit_model(self):
        bm = BenefitModel(
            id="BM-1",
            name="自动化节省工时",
            benefit_type="efficiency",
            estimated_value=50000.0,
            unit="元/年",
        )
        assert bm.benefit_type == "efficiency"
        assert bm.estimated_value == 50000.0


class TestTransition:
    def test_create_transition(self):
        t = Transition(
            id="T-1",
            from_stage=LifecycleStage.PLANNING,
            to_stage=LifecycleStage.DESIGN,
            triggered_by="OKR 审批通过",
        )
        assert t.status == "pending"
        assert t.from_stage == LifecycleStage.PLANNING
        assert t.to_stage == LifecycleStage.DESIGN


class TestM3ElementType:
    def test_lifecycle_elements(self):
        assert M3ElementType.STAGE.value == "Stage"
        assert M3ElementType.GATE.value == "Gate"

    def test_value_elements(self):
        assert M3ElementType.GOAL.value == "Goal"
        assert M3ElementType.COST_MODEL.value == "CostModel"
