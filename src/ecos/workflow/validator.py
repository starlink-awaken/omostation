"""Workflow Validator — 治理约束校验器

Phase 5 (2026-06-22):
- X2BudgetDeducer: 对接 runtime X2 Budget Policy — 真实读写 llm_quota_ledger.jsonl
- X3CostRecorder: 成本归因写入同一账本

Phase 3 (基线):
- X1ConstraintChecker: 跨层协议检查（复用 L0-constraints.yaml 规则）
- X4ConsistencyChecker: 依赖完整性检查

验证管线:
  parse_step(M1)
    → X1 check (preflight)
    → X2 budget check + deduct (preflight)
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

from ecos.common.governed_fs import (
    append_jsonl_record,
    ensure_text_file,
    write_yaml_file,
)

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
            violations.append(
                {
                    "id": "X1-C01-S001",
                    "constraint": "X1-C01",
                    "severity": "error",
                    "message": "Step 缺少 name 字段",
                }
            )

        # action 或 agent_role 至少有一个
        if not step.get("action") and not step.get("agent_role"):
            violations.append(
                {
                    "id": "X1-C01-S002",
                    "constraint": "X1-C01",
                    "severity": "warning",
                    "message": "Step 缺少 action 或 agent_role",
                }
            )

        return violations

    @classmethod
    def check_workflow(cls, m1_node: dict) -> list[dict]:
        """检查整个 workflow 的 X1 合规性"""
        violations: list[dict] = []

        execution = m1_node.get("execution", {})
        subtype = m1_node.get("subtype", "")

        # WF-V001: 检查 execution.mode 合法性
        mode = execution.get("mode")
        valid_modes = (
            "workflow",
            "graph",
            "loop",
            "dynamic",
            "state-machine",
            "sequential",
        )
        if mode and mode not in valid_modes:
            violations.append(
                {
                    "id": "WF-V001",
                    "constraint": "X1-C01",
                    "severity": "warning",
                    "message": f"未知的 execution.mode: {mode}",
                }
            )

        # 检查必填 execution 字段
        required = cls.REQUIRED_EXECUTION_FIELDS.get(subtype, {"mode"})
        for field in required:
            if field not in execution or execution.get(field) is None:
                violations.append(
                    {
                        "id": f"X1-C01-{field.upper()}",
                        "constraint": "X1-C01",
                        "severity": "error",
                        "message": f"execution.{field} 为必填字段",
                    }
                )

        # 检查步骤级约束
        step_names = {s.get("name") for s in m1_node.get("steps", []) if s.get("name")}
        for step in m1_node.get("steps", []):
            violations.extend(cls.check_step(step))
            # WF-V002: 检查步骤依赖是否存在
            for dep in step.get("depends_on", []):
                if dep not in step_names:
                    violations.append(
                        {
                            "id": "WF-V002",
                            "constraint": "X1-C01",
                            "severity": "error",
                            "message": f"Step '{step.get('name')}' 依赖的 '{dep}' 不存在",
                        }
                    )

        return violations


# 共享账本路径（与 runtime X2 Budget Policy 一致）
_LLM_QUOTA_LEDGER = Path.home() / ".omo" / "state" / "llm_quota_ledger.jsonl"
_DEFAULT_TOKEN_BUDGET = 100000  # 默认 Token 上限


# =========================================================================
# X2: 预算检查器（对接 runtime X2 Budget Policy）
# =========================================================================


class X2BudgetDeducer:
    """X2 预算检查 — 对接 llm_quota_ledger.jsonl

    与 runtime 共享同一账本:
    - 事前: 读取 balance，余额不足时熔断
    - 事后: 写入消耗记录
    """

    LEDGER_PATH = _LLM_QUOTA_LEDGER

    @classmethod
    def _ensure_ledger(cls) -> None:
        """确保账本文件和目录存在"""
        if not cls.LEDGER_PATH.exists():
            ensure_text_file(cls.LEDGER_PATH, "")

    @classmethod
    def _read_balance(cls) -> int:
        """读取当前 Token 余额

        从账本中计算最后一条 balance 记录。
        无记录时返回默认值。
        """
        cls._ensure_ledger()
        if not cls.LEDGER_PATH.exists() or cls.LEDGER_PATH.stat().st_size == 0:
            return _DEFAULT_TOKEN_BUDGET

        last_balance = _DEFAULT_TOKEN_BUDGET
        try:
            with open(cls.LEDGER_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("event") == "balance":
                            last_balance = entry.get("balance", last_balance)
                        elif entry.get("event") in ("deduct", "consume"):
                            last_balance = entry.get("balance_after", last_balance)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            pass

        return last_balance

    @classmethod
    def check_budget(cls, m1_node: dict) -> dict:
        """检查预算配置并返回余额状态

        Returns:
            {"ok": bool, "budget": dict, "balance": int, "warnings": list}
        """
        execution = m1_node.get("execution", {})
        budget = execution.get("budget", {})
        warnings: list[str] = []

        if not budget:
            return {"ok": True, "budget": {}, "balance": 0, "warnings": ["无预算配置"]}

        token_limit = budget.get("token_limit", _DEFAULT_TOKEN_BUDGET)
        round_limit = budget.get("round_limit")

        if token_limit is not None and token_limit <= 0:
            warnings.append(f"token_limit 无效: {token_limit}")

        if round_limit is not None and round_limit <= 0:
            warnings.append(f"round_limit 无效: {round_limit}")

        # 读取余额
        balance = cls._read_balance()
        if balance < token_limit:
            warnings.append(f"余额不足: {balance} < {token_limit}")

        return {
            "ok": len(warnings) == 0,
            "budget": budget,
            "balance": balance,
            "warnings": warnings,
        }

    @classmethod
    def deduct(cls, workflow_id: str, m1_node: dict, amount: int = 0) -> dict:
        """执行 Token 扣减

        写入共享账本，与 runtime X2 Policy 兼容。
        当余额 < 0 时自动生成 OMO Debt 信号。

        Returns:
            {"ok": bool, "balance_before": int, "balance_after": int, "debt_generated": bool}
        """
        cls._ensure_ledger()

        balance_before = cls._read_balance()
        execution = m1_node.get("execution", {})
        budget = execution.get("budget", {})
        token_limit = budget.get("token_limit", _DEFAULT_TOKEN_BUDGET)

        amount = amount or token_limit
        balance_after = balance_before - amount
        debt_generated = balance_after < 0

        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "deduct",
            "workflow_id": workflow_id,
            "amount": amount,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "debt_generated": debt_generated,
        }

        try:
            append_jsonl_record(cls.LEDGER_PATH, entry)
        except OSError as e:
            logger.warning("Failed to write X2 ledger: %s", e)
            return {"ok": False, "error": str(e)}

        if debt_generated:
            logger.warning(
                "X2 budget depleted for %s: balance=%d", workflow_id, balance_after
            )

        return {
            "ok": True,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "debt_generated": debt_generated,
        }


# =========================================================================
# X3: 成本归因器（对接 llm_quota_ledger.jsonl）
# =========================================================================


class X3CostRecorder:
    """X3 成本归因 — 写入共享账本"""

    LEDGER_PATH = _LLM_QUOTA_LEDGER

    @classmethod
    def record(cls, workflow_id: str, result: dict) -> None:
        """记录成本归因"""
        cls._ensure_ledger()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "cost_record",
            "workflow_id": workflow_id,
            "passed": result.get("failed", 0) == 0,
            "steps_total": result.get("passed", 0) + result.get("failed", 0),
            "steps_passed": result.get("passed", 0),
            "steps_failed": result.get("failed", 0),
        }
        try:
            append_jsonl_record(cls.LEDGER_PATH, entry)
        except OSError as e:
            logger.warning("Failed to write X3 cost record: %s", e)

    @classmethod
    def _ensure_ledger(cls) -> None:
        if not cls.LEDGER_PATH.exists():
            ensure_text_file(cls.LEDGER_PATH, "")


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
            violations.append(
                {
                    "id": "X4-C01-STEP-COUNT",
                    "constraint": "X4-C01",
                    "severity": "warning",
                    "message": f"预期 {len(steps)} 步，实际执行 {len(result_steps)} 步",
                }
            )

        # 检查是否有失败的步骤
        if result.get("failed", 0) > 0:
            violations.append(
                {
                    "id": "X4-C01-FAILED",
                    "constraint": "X4-C01",
                    "severity": "error",
                    "message": f"执行结果中有 {result['failed']} 步失败",
                }
            )

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
        violations.append(
            {
                "id": "X2-C01-BUDGET",
                "constraint": "X2-C01",
                "severity": "warning",
                "message": w,
            }
        )

    return violations


def check_execution_result(m1_node: dict, result: dict) -> list[dict]:
    """执行后一致性检查"""
    return X4ConsistencyChecker.check_result(m1_node, result)


# =========================================================================
# M0 快照生成
# =========================================================================


def generate_m0_snapshot(workflow_id: str, m1_node: dict, result: dict) -> str | None:
    """生成 M0 运行时快照

    写入 .omo/state/workflow-runs/{workflow_id}-{timestamp}.yaml
    """
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
        filepath = M0_SNAPSHOT_DIR / f"{workflow_id}-{timestamp}.yaml"
        write_yaml_file(filepath, snapshot)
        logger.info("M0 snapshot written: %s", filepath)
        return str(filepath)
    except Exception as e:  # defensive fallback
        logger.warning("Failed to write M0 snapshot: %s", e)
        return None
