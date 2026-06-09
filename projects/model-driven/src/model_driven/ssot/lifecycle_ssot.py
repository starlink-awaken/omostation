"""
model_driven.ssot — SSOT 全生命周期化

将 SSOT 原则扩展到全生命周期：
- 生命周期 SSOT: 阶段状态单一事实源
- 价值体系 SSOT: 成本/收益单一事实源
- 过程 SSOT: 流程步骤单一事实源
- 跨阶段一致性检查
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from model_driven.constants import PERCENT_MULTIPLIER
from model_driven.mof.m3_extended import LifecycleStage


@dataclass
class SSOTSnapshot:
    """SSOT 快照"""

    id: str
    entity_type: str = ""
    entity_id: str = ""
    stage: LifecycleStage | None = None
    data: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class LifecycleSSOT:
    """生命周期 SSOT — 维护每个阶段状态的唯一事实源"""

    def __init__(self):
        self._snapshots: dict[str, list[SSOTSnapshot]] = {}  # entity_id → snapshots
        self._current_state: dict[str, dict[str, Any]] = {}  # entity_id → current_state

    def record_snapshot(self, snapshot: SSOTSnapshot) -> None:
        """记录快照"""
        key = snapshot.entity_id
        if key not in self._snapshots:
            self._snapshots[key] = []
        self._snapshots[key].append(snapshot)
        self._current_state[key] = snapshot.data

    def get_current_state(self, entity_id: str) -> dict[str, Any] | None:
        """获取当前状态"""
        return self._current_state.get(entity_id)

    def get_history(self, entity_id: str) -> list[SSOTSnapshot]:
        """获取历史快照"""
        return self._snapshots.get(entity_id, [])

    def detect_drift(self, entity_id: str, declared_state: dict[str, Any]) -> list[dict[str, Any]]:
        """检测漂移 (声明的 vs 实际的)"""
        current = self._current_state.get(entity_id, {})
        drifts = []
        for key, value in declared_state.items():
            if key in current and current[key] != value:
                drifts.append(
                    {
                        "entity_id": entity_id,
                        "field": key,
                        "declared": value,
                        "actual": current[key],
                    }
                )
        return drifts


class ValueSSOT:
    """价值体系 SSOT — 维护成本和收益的单一事实源"""

    def __init__(self):
        self._costs: dict[str, list[dict[str, Any]]] = {}
        self._benefits: dict[str, list[dict[str, Any]]] = {}
        self._roi_analyses: dict[str, dict[str, Any]] = {}

    def record_cost(self, entity_id: str, cost_data: dict[str, Any]) -> None:
        """记录成本"""
        if entity_id not in self._costs:
            self._costs[entity_id] = []
        self._costs[entity_id].append(
            {
                **cost_data,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )

    def record_benefit(self, entity_id: str, benefit_data: dict[str, Any]) -> None:
        """记录收益"""
        if entity_id not in self._benefits:
            self._benefits[entity_id] = []
        self._benefits[entity_id].append(
            {
                **benefit_data,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )

    def get_total_cost(self, entity_id: str) -> float:
        """获取总成本"""
        records = self._costs.get(entity_id, [])
        return sum(r.get("amount", 0) for r in records)

    def get_total_benefit(self, entity_id: str) -> float:
        """获取总收益"""
        records = self._benefits.get(entity_id, [])
        return sum(r.get("amount", 0) for r in records)

    def calculate_roi(self, entity_id: str) -> dict[str, Any]:
        """计算 ROI"""
        total_cost = self.get_total_cost(entity_id)
        total_benefit = self.get_total_benefit(entity_id)
        roi = (total_benefit - total_cost) / total_cost if total_cost > 0 else 0

        analysis = {
            "entity_id": entity_id,
            "total_cost": total_cost,
            "total_benefit": total_benefit,
            "roi": round(roi, 4),
            "roi_pct": round(roi * PERCENT_MULTIPLIER, 1),
            "calculated_at": datetime.now(UTC).isoformat(),
        }
        self._roi_analyses[entity_id] = analysis
        return analysis


class ProcessSSOT:
    """过程 SSOT — 维护流程步骤的单一事实源"""

    def __init__(self):
        self._processes: dict[str, dict[str, Any]] = {}
        self._step_executions: dict[str, list[dict[str, Any]]] = {}

    def define_process(self, process_id: str, definition: dict[str, Any]) -> None:
        """定义流程"""
        self._processes[process_id] = {
            **definition,
            "defined_at": datetime.now(UTC).isoformat(),
        }

    def record_step_execution(
        self,
        process_id: str,
        step_id: str,
        status: str,
        output: Any = None,
    ) -> None:
        """记录步骤执行"""
        key = f"{process_id}:{step_id}"
        if key not in self._step_executions:
            self._step_executions[key] = []
        self._step_executions[key].append(
            {
                "process_id": process_id,
                "step_id": step_id,
                "status": status,
                "output": output,
                "executed_at": datetime.now(UTC).isoformat(),
            }
        )

    def get_process_progress(self, process_id: str) -> dict[str, Any]:
        """获取流程进度"""
        definition = self._processes.get(process_id, {})
        steps = definition.get("steps", [])
        total = len(steps)
        completed = 0
        for s in steps:
            executions = self._step_executions.get(f"{process_id}:{s['id']}", [])
            if executions and executions[-1].get("status") == "completed":
                completed += 1
        return {
            "process_id": process_id,
            "total_steps": total,
            "completed_steps": completed,
            "progress": round(completed / total * PERCENT_MULTIPLIER, 1) if total > 0 else 0,
        }


class CrossStageConsistencyChecker:
    """跨阶段一致性检查器"""

    def check(
        self,
        planning_models: list[dict[str, Any]],
        design_models: list[dict[str, Any]],
        dev_models: list[dict[str, Any]],
        deploy_models: list[dict[str, Any]],
        runtime_models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """执行跨阶段一致性检查"""
        issues = []

        # CS-01: 规划→设计一致性
        spec_ids = {m.get("id") for m in design_models if m.get("type") == "spec_design"}
        okr_ids = {m.get("id") for m in planning_models if m.get("type") == "okr"}
        # 检查每个 Spec 是否有关联 OKR
        for spec in design_models:
            if spec.get("type") == "spec_design":
                related = spec.get("properties", {}).get("related_okrs", [])
                if not related:
                    issues.append(
                        {
                            "rule": "CS-01",
                            "severity": "error",
                            "message": f"Spec {spec.get('id')} ({spec.get('name', '?')}) 未关联任何 OKR (可用 OKR: {list(okr_ids)[:3]})",
                            "spec_id": spec.get("id"),
                            "spec_name": spec.get("name", ""),
                            "available_okrs": list(okr_ids),
                        }
                    )

        # CS-02: 设计→开发一致性
        for code_mod in dev_models:
            if code_mod.get("type") == "code_module":
                if not spec_ids:
                    issues.append(
                        {
                            "rule": "CS-02",
                            "severity": "warning",
                            "message": f"代码模块 {code_mod.get('id')} ({code_mod.get('name', '?')}) 无对应 Spec (可用 Spec: {list(spec_ids)[:3]})",
                            "code_module_id": code_mod.get("id"),
                            "available_specs": list(spec_ids),
                        }
                    )

        # CS-04: 部署→运行一致性
        runtime_services = {m.get("id") for m in runtime_models if m.get("type") == "alert_rule"}
        for deploy in deploy_models:
            if deploy.get("type") == "deployment_config":
                if not runtime_services:
                    issues.append(
                        {
                            "rule": "CS-04",
                            "severity": "error",
                            "message": f"部署配置 {deploy.get('id')} ({deploy.get('name', '?')}) 无对应告警规则",
                            "deploy_id": deploy.get("id"),
                        }
                    )

        return {
            "checked_at": datetime.now(UTC).isoformat(),
            "total_issues": len(issues),
            "passed": len(issues) == 0,
            "issues": issues,
        }
