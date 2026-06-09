"""
model_driven.lifecycle.gates — 门禁检查引擎

实现阶段间的门禁检查：
- 检查项执行
- 门禁通过/失败判定
- 审批流程
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from model_driven.mof.m3_extended import Gate, LifecycleStage, STANDARD_GATES


class GateResult(Enum):
    """门禁检查结果"""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """单个检查项的结果"""

    name: str
    check_type: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class GateExecution:
    """门禁执行记录"""

    gate: Gate
    result: GateResult = GateResult.PENDING
    check_results: list[CheckResult] = field(default_factory=list)
    executed_at: str = ""
    approved_by: list[str] = field(default_factory=list)
    notes: str = ""


class GateEngine:
    """门禁检查引擎"""

    def __init__(self, gates: list[Gate] | None = None):
        self._gates = gates or list(STANDARD_GATES)
        self._custom_checks: dict[str, callable] = {}

    def register_check(self, check_type: str, check_fn: callable) -> None:
        """注册自定义检查函数"""
        self._custom_checks[check_type] = check_fn

    def get_gate(self, from_stage: LifecycleStage, to_stage: LifecycleStage) -> Gate | None:
        """获取两个阶段之间的门禁"""
        for gate in self._gates:
            if gate.from_stage == from_stage and gate.to_stage == to_stage:
                return gate
        return None

    def check_gate(
        self,
        gate: Gate,
        context: dict[str, Any] | None = None,
    ) -> GateExecution:
        """执行门禁检查"""
        context = context or {}
        execution = GateExecution(gate=gate, executed_at=datetime.now(timezone.utc).isoformat())

        if gate.auto_pass:
            execution.result = GateResult.PASSED
            execution.notes = "自动通过"
            return execution

        all_passed = True
        for check in gate.checks:
            check_type = check.get("type", "")
            check_name = check.get("name", "未命名检查")
            required = check.get("required", True)

            if not required:
                execution.check_results.append(CheckResult(
                    name=check_name,
                    check_type=check_type,
                    passed=True,
                    message="非必需检查，已跳过",
                ))
                continue

            # 执行检查
            result = self._execute_check(check, context)
            execution.check_results.append(result)

            if not result.passed:
                all_passed = False

        execution.result = GateResult.PASSED if all_passed else GateResult.FAILED
        return execution

    def _execute_check(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """执行单个检查项"""
        check_type = check.get("type", "")
        check_name = check.get("name", "未命名检查")

        # 1. 自定义检查函数
        if check_type in self._custom_checks:
            try:
                passed, message = self._custom_checks[check_type](check, context)
                return CheckResult(name=check_name, check_type=check_type, passed=passed, message=message)
            except Exception as e:
                return CheckResult(name=check_name, check_type=check_type, passed=False, message=str(e))

        # 2. 内置检查类型
        if check_type == "approval":
            return self._check_approval(check, context)
        elif check_type == "document":
            return self._check_document(check, context)
        elif check_type == "review":
            return self._check_review(check, context)
        elif check_type == "metric":
            return self._check_metric(check, context)
        elif check_type == "test":
            return self._check_test(check, context)
        elif check_type == "ci":
            return self._check_ci(check, context)
        elif check_type == "deploy":
            return self._check_deploy(check, context)
        elif check_type == "config":
            return self._check_config(check, context)
        else:
            return CheckResult(
                name=check_name,
                check_type=check_type,
                passed=False,
                message=f"未知检查类型: {check_type}",
            )

    def _check_approval(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """审批检查"""
        approvals = context.get("approvals", {})
        check_name = check.get("name", "审批检查")
        if approvals.get(check_name, False):
            return CheckResult(name=check_name, check_type="approval", passed=True, message="已审批")
        return CheckResult(name=check_name, check_type="approval", passed=False, message="未审批")

    def _check_document(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """文档检查"""
        documents = context.get("documents", {})
        check_name = check.get("name", "文档检查")
        if check_name in documents and documents[check_name]:
            return CheckResult(name=check_name, check_type="document", passed=True, message="文档已完成")
        return CheckResult(name=check_name, check_type="document", passed=False, message="文档未完成")

    def _check_review(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """评审检查"""
        reviews = context.get("reviews", {})
        check_name = check.get("name", "评审检查")
        if reviews.get(check_name, False):
            return CheckResult(name=check_name, check_type="review", passed=True, message="评审已通过")
        return CheckResult(name=check_name, check_type="review", passed=False, message="评审未通过")

    def _check_metric(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """指标检查"""
        check_name = check.get("name", "指标检查")
        threshold = check.get("threshold", 0)
        metrics = context.get("metrics", {})
        metric_key = check_name
        actual = metrics.get(metric_key, 0)
        if actual >= threshold:
            return CheckResult(
                name=check_name, check_type="metric", passed=True,
                message=f"指标达标: {actual} >= {threshold}",
                details={"actual": actual, "threshold": threshold},
            )
        return CheckResult(
            name=check_name, check_type="metric", passed=False,
            message=f"指标不达标: {actual} < {threshold}",
            details={"actual": actual, "threshold": threshold},
        )

    def _check_test(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """测试检查"""
        test_results = context.get("test_results", {})
        check_name = check.get("name", "测试检查")
        if test_results.get(check_name, False):
            return CheckResult(name=check_name, check_type="test", passed=True, message="测试通过")
        return CheckResult(name=check_name, check_type="test", passed=False, message="测试未通过")

    def _check_ci(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """CI 检查"""
        ci_status = context.get("ci_status", "unknown")
        check_name = check.get("name", "CI 检查")
        if ci_status == "success":
            return CheckResult(name=check_name, check_type="ci", passed=True, message="CI 绿灯")
        return CheckResult(name=check_name, check_type="ci", passed=False, message=f"CI 状态: {ci_status}")

    def _check_deploy(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """部署检查"""
        deploy_status = context.get("deploy_status", "unknown")
        check_name = check.get("name", "部署检查")
        if deploy_status == "success":
            return CheckResult(name=check_name, check_type="deploy", passed=True, message="部署成功")
        return CheckResult(name=check_name, check_type="deploy", passed=False, message=f"部署状态: {deploy_status}")

    def _check_config(self, check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
        """配置检查"""
        configs = context.get("configs", {})
        check_name = check.get("name", "配置检查")
        if configs.get(check_name, False):
            return CheckResult(name=check_name, check_type="config", passed=True, message="配置已完成")
        return CheckResult(name=check_name, check_type="config", passed=False, message="配置未完成")

    def can_transition(
        self,
        from_stage: LifecycleStage,
        to_stage: LifecycleStage,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, GateExecution | None]:
        """检查是否可以从 from_stage 转换到 to_stage"""
        gate = self.get_gate(from_stage, to_stage)
        if gate is None:
            return True, None  # 无门禁，允许通过

        execution = self.check_gate(gate, context)
        return execution.result == GateResult.PASSED, execution
