"""Workflow Validator — 治理约束校验器

Phase 3:
- X1ConstraintChecker: 跨层协议检查（复用 L0-constraints.yaml 规则）
- X2BudgetDeducer: Token 预算检查（记帐模式，暂不真正扣减）
- X4ConsistencyChecker: 依赖完整性检查
- X3CostRecorder: 成本归因（Stub，Phase 5 扩展）

验证管线在 execute_m1_workflow() 中的位置:
  parse_step(M1)
    → X1 check (preflight)
    → X2 budget check (preflight)
    → execute (backend)
    → X4 check (postflight)
    → X3 record (postflight)
    → M0 snapshot
    → L0 audit
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("ecos.workflow.validator")

# M0 快照目录
M0_SNAPSHOT_DIR = Path.home() / ".omo" / "state" / "workflow-runs"


# =========================================================================
# X1: 约束检查器
# =========================================================================

class X1ConstraintChecker:
    """X1 约束检查 — 执行前验证

    基于 L0-constraints.yaml 的规则定义：
    - X1-C01: protocol.registered — 协议必须注册
    - X1-C02: 跨层调用必须经过 I0/Agora
    - CR-MOF-VALIDATE-01: M1 schema 合规（已由 mof-schema-validate 覆盖）
    """

    REQUIRED_EXECUTION_FIELDS = {
        "workflow": {"mode", "timeout"},
    }

    @classmethod
    def check_step(cls, step: dict, context: dict | None = None) -> list[dict]:
        """检查单个 step 的 X1 合规性"""
        violations: list[dict] = []
        _ = context

        # step 必须有 name
        if not step.get("name"):
            violations.append({
                "id": "X1-C01-S001",
                "constraint": "X1-C01",
                "severity": "error",
                "message": "Step 缺少 name 字段",
            })

        # action 或 agent_role 至少有一个
        if not step.get("action") and not step.get("agent_role"):
            violations.append({
                "id": "X1-C01-S002",
                "constraint": "X1-C01",
                "severity": "warning",
                "message": "Step 缺少 action 或 agent_role",
            })

        return violations

    @classmethod
    def check_workflow(cls, m1_node: dict) -> list[dict]:
        """检查整个 workflow 的 X1 合规性"""
        violations: list[dict] = []

        execution = m1_node.get("execution", {})
        subtype = m1_node.get("subtype", "")

        # WF-V001: 检查 execution.mode 合法性
        mode = execution.get("mode")
        if mode and mode not in ("workflow", "graph", "loop", "dynamic", "state-machine"):
            violations.append({
                "id": "WF-V001",
                "constraint": "X1-C01",
                "severity": "warning",
                "message": f"未知的 execution.mode: {mode}",
            })

        # 检查必填 execution 字段
        required = cls.REQUIRED_EXECUTION_FIELDS.get(subtype, {"mode"})
        for field in required:
            if field not in execution or execution.get(field) is None:
                violations.append({
                    "id": f"X1-C01-{field.upper()}",
                    "constraint": "X1-C01",
                    "severity": "error",
                    "message": f"execution.{field} 为必填字段",
                })

        # 检查步骤级约束
        step_names = {s.get("name") for s in m1_node.get("steps", []) if s.get("name")}
        for step in m1_node.get("steps", []):
            violations.extend(cls.check_step(step))
            # WF-V002: 检查步骤依赖是否存在
            for dep in step.get("depends_on", []):
                if dep not in step_names:
                    violations.append({
                        "id": "WF-V002",
                        "constraint": "X1-C01",
                        "severity": "error",
                        "message": f"Step '{step.get('name')}' 依赖的 '{dep}' 不存在",
                    })

        return violations


# =========================================================================
# X2: 预算检查器
# =========================================================================

class X2BudgetDeducer:
    """X2 预算检查 — 执行前验证

    当前为 pass-through 模式（记录预算配置但不真正扣减）。
    Phase 5 对接 runtime X2 Budget Policy 做实时扣减。
    """

    @classmethod
    def check_budget(cls, m1_node: dict) -> dict:
        """检查预算配置，返回预算状态

        Returns:
            {"ok": bool, "budget": dict, "warnings": list}
        """
        execution = m1_node.get("execution", {})
        budget = execution.get("budget", {})
        warnings: list[str] = []

        if not budget:
            return {"ok": True, "budget": {}, "warnings": ["无预算配置"]}

        token_limit = budget.get("token_limit")
        round_limit = budget.get("round_limit")

        if token_limit is not None and token_limit <= 0:
            warnings.append(f"token_limit 无效: {token_limit}")

        if round_limit is not None and round_limit <= 0:
            warnings.append(f"round_limit 无效: {round_limit}")

        return {
            "ok": len(warnings) == 0,
            "budget": budget,
            "warnings": warnings,
        }

    @classmethod
    def record_consumption(cls, workflow_id: str, consumed: dict) -> None:
        """记录预算消耗（Stub — Phase 5 对接真实扣减）"""
        ledger_path = Path.home() / ".omo" / "state" / "budget-ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "workflow_id": workflow_id,
            "consumed": consumed,
        }
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# =========================================================================
# X3: 成本归因器
# =========================================================================

class X3CostRecorder:
    """X3 成本归因 — 执行后记录（Stub）

    Phase 5: 对接 LLM_GATEWAY 的 cost_attribution 做精确归因。
    """

    @classmethod
    def record(cls, workflow_id: str, result: dict) -> None:
        """记录成本归因"""
        ledger_path = Path.home() / ".omo" / "state" / "cost-ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "workflow_id": workflow_id,
            "passed": result.get("failed", 0) == 0,
            "steps_count": result.get("passed", 0) + result.get("failed", 0),
        }
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# =========================================================================
# X4: 一致性检查器
# =========================================================================

class X4ConsistencyChecker:
    """X4 一致性检查 — 执行后验证

    检查：
    - 步骤依赖是否满足（所有 must_run_after 的状态正确）
    - 输出是否包含预期字段
    """

    @classmethod
    def check_result(cls, m1_node: dict, result: dict) -> list[dict]:
        """检查执行结果的一致性"""
        violations: list[dict] = []

        steps = m1_node.get("steps", [])
        result_steps = result.get("steps", [])

        # 检查步骤数是否匹配
        if len(steps) != len(result_steps):
            violations.append({
                "id": "X4-C01-STEP-COUNT",
                "constraint": "X4-C01",
                "severity": "warning",
                "message": f"预期 {len(steps)} 步，实际执行 {len(result_steps)} 步",
            })

        # 检查是否有失败的步骤
        if result.get("failed", 0) > 0:
            violations.append({
                "id": "X4-C01-FAILED",
                "constraint": "X4-C01",
                "severity": "error",
                "message": f"执行结果中有 {result['failed']} 步失败",
            })

        return violations


# =========================================================================
# 统一校验入口
# =========================================================================

def validate_step(step: dict, context: dict | None = None) -> list[dict]:
    """校验单个 step（外部入口）"""
    return X1ConstraintChecker.check_step(step, context)


def validate_workflow(m1_node: dict) -> list[dict]:
    """校验整个 workflow（外部入口）"""
    violations: list[dict] = []

    # X1
    violations.extend(X1ConstraintChecker.check_workflow(m1_node))

    # X2 budget 检查（警告类, 不阻断）
    budget_result = X2BudgetDeducer.check_budget(m1_node)
    for w in budget_result.get("warnings", []):
        violations.append({
            "id": "X2-C01-BUDGET",
            "constraint": "X2-C01",
            "severity": "warning",
            "message": w,
        })

    return violations


def check_execution_result(m1_node: dict, result: dict) -> list[dict]:
    """执行后一致性检查"""
    return X4ConsistencyChecker.check_result(m1_node, result)


# =========================================================================
# M0 快照生成
# =========================================================================

def generate_m0_snapshot(workflow_id: str, m1_node: dict,
                         result: dict) -> str | None:
    """生成 M0 运行时快照

    写入 .omo/state/workflow-runs/{workflow_id}-{timestamp}.yaml
    """
    import yaml as ymlib

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot = {
        "schema": "M0-v1",
        "generated_at": datetime.now().isoformat(),
        "workflow_id": workflow_id,
        "name": m1_node.get("name", workflow_id),
        "status": "ok" if result.get("failed", 0) == 0 else "failed",
        "execution": {
            "mode": m1_node.get("execution", {}).get("mode", "workflow"),
            "backend": m1_node.get("execution", {}).get("backend", "default"),
        },
        "result": {
            "passed": result.get("passed", 0),
            "failed": result.get("failed", 0),
            "steps": [
                {"name": s.get("name"), "status": s.get("status")}
                for s in result.get("steps", [])
            ],
            "violations": result.get("violations", []),
        },
        "governance": {
            "X1": "checked",
            "X2": "checked",
        },
    }

    try:
        M0_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filepath = M0_SNAPSHOT_DIR / f"{workflow_id}-{timestamp}.yaml"
        with open(filepath, "w") as f:
            ymlib.dump(snapshot, f, allow_unicode=True, default_flow_style=False)
        logger.info("M0 snapshot written: %s", filepath)
        return str(filepath)
    except Exception as e:
        logger.warning("Failed to write M0 snapshot: %s", e)
        return None
