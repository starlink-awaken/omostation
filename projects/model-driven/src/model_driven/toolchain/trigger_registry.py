"""
model_driven.toolchain.trigger_registry — Trigger 统一注册与管理

统一管理所有异步触发机制:
- 注册: 从 M1 节点加载 Trigger 定义
- 查询: 按类型/状态/层过滤
- 健康检查: 集成 TriggerM0Manager 获取运行时状态
- 推导: 集成 DerivationEngine 执行 DR-TRIGGER 规则
- 治理: 集成 OMOBridge 自动注册 Debt/创建 Task/记录 Audit
- 仪表板: 统一健康视图

对外接口:
- CLI: model-driven trigger <list|status|derive|heal|dashboard>
- MCP: trigger_list/trigger_status/trigger_derive/trigger_heal/trigger_dashboard
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from model_driven.constants import MAX_HEALTH_SCORE
from model_driven.toolchain.derivation_engine import DerivationEngine
from model_driven.toolchain.trigger_m0 import TriggerM0Manager, TriggerRuntimeSnapshot


@dataclass
class TriggerInfo:
    """Trigger 统一信息视图 — 整合 M1 声明 + M0 运行时状态"""

    trigger_id: str
    name: str
    trigger_type: str
    layer: str
    status: str  # M1 声明状态
    m0_status: str = "unknown"  # M0 运行时状态
    schedule: str = ""
    dependencies: list[str] = field(default_factory=list)
    health_score: float = MAX_HEALTH_SCORE
    last_execution: str = ""
    consecutive_failures: int = 0
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "layer": self.layer,
            "status": self.status,
            "m0_status": self.m0_status,
            "schedule": self.schedule,
            "dependencies": self.dependencies,
            "health_score": self.health_score,
            "last_execution": self.last_execution,
            "consecutive_failures": self.consecutive_failures,
            "source": self.source,
        }


class TriggerRegistry:
    """Trigger 统一注册与管理器

    整合:
    - M1 节点加载 (ecos/mof/m1/trigger/*.yaml)
    - M0 运行时状态 (TriggerM0Manager)
    - 推导规则 (DerivationEngine)
    - 治理闭环 (OMOBridge)
    """

    def __init__(self, m1_dir: str | None = None):
        if m1_dir is None:
            from model_driven._paths import get_workspace_dir

            ws = str(get_workspace_dir())
            self._m1_dir = Path(ws) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"
        else:
            self._m1_dir = Path(m1_dir)

        self._triggers: dict[str, dict[str, Any]] = {}
        self._m0_manager = TriggerM0Manager()
        self._derivation_engine = DerivationEngine()
        self._load_m1_nodes()
        self._m0_manager.load()

    def _load_m1_nodes(self) -> None:
        """从 M1 节点加载 Trigger 定义"""
        if not self._m1_dir.exists():
            return
        for f in sorted(self._m1_dir.glob("*.yaml")):
            try:
                with open(f) as fh:
                    data = yaml.safe_load(fh)
                if data and data.get("type") == "trigger":
                    self._triggers[data["id"]] = data
            except (OSError, yaml.YAMLError, KeyError):
                pass

    def reload(self) -> int:
        """重新加载 M1 节点"""
        self._triggers.clear()
        self._load_m1_nodes()
        return len(self._triggers)

    # ── 查询 ──────────────────────────────────────

    def list_all(self, trigger_type: str | None = None, layer: str | None = None) -> list[TriggerInfo]:
        """列出所有 Trigger，支持按类型/层过滤"""
        result = []
        for tid, m1 in self._triggers.items():
            ttype = m1.get("properties", {}).get("trigger_type", "unknown")
            tlayer = m1.get("layer", "")

            if trigger_type and ttype != trigger_type:
                continue
            if layer and tlayer != layer:
                continue

            m0 = self._m0_manager.get_snapshot(tid)
            info = TriggerInfo(
                trigger_id=tid,
                name=m1.get("name", tid),
                trigger_type=ttype,
                layer=tlayer,
                status=m1.get("status", "unknown"),
                m0_status=m0.status if m0 else "unknown",
                schedule=m1.get("properties", {}).get("schedule", ""),
                dependencies=m1.get("properties", {}).get("dependencies", []),
                health_score=m0.health_score if m0 else MAX_HEALTH_SCORE,
                last_execution=m0.last_execution if m0 else "",
                consecutive_failures=m0.consecutive_failures if m0 else 0,
                source=m1.get("source", ""),
            )
            result.append(info)
        return result

    def get_trigger(self, trigger_id: str) -> TriggerInfo | None:
        """获取单个 Trigger 的完整信息"""
        m1 = self._triggers.get(trigger_id)
        if not m1:
            return None
        m0 = self._m0_manager.get_snapshot(trigger_id)
        return TriggerInfo(
            trigger_id=trigger_id,
            name=m1.get("name", trigger_id),
            trigger_type=m1.get("properties", {}).get("trigger_type", "unknown"),
            layer=m1.get("layer", ""),
            status=m1.get("status", "unknown"),
            m0_status=m0.status if m0 else "unknown",
            schedule=m1.get("properties", {}).get("schedule", ""),
            dependencies=m1.get("properties", {}).get("dependencies", []),
            health_score=m0.health_score if m0 else MAX_HEALTH_SCORE,
            last_execution=m0.last_execution if m0 else "",
            consecutive_failures=m0.consecutive_failures if m0 else 0,
            source=m1.get("source", ""),
        )

    def list_types(self) -> list[str]:
        """列出所有 Trigger 类型"""
        types = set()
        for m1 in self._triggers.values():
            types.add(m1.get("properties", {}).get("trigger_type", "unknown"))
        return sorted(types)

    def list_layers(self) -> list[str]:
        """列出所有层"""
        layers = set()
        for m1 in self._triggers.values():
            layers.add(m1.get("layer", ""))
        return sorted(layers)

    # ── 健康检查 ──────────────────────────────────

    def check_health(self, trigger_id: str | None = None) -> dict[str, Any]:
        """检查 Trigger 健康状态

        Args:
            trigger_id: 指定 Trigger ID 或 None (全部)
        """
        if trigger_id:
            info = self.get_trigger(trigger_id)
            if not info:
                return {"error": f"Trigger not found: {trigger_id}"}
            return {
                "trigger": info.to_dict(),
                "m0_snapshot": self._m0_manager.get_snapshot(trigger_id).to_dict()
                if self._m0_manager.get_snapshot(trigger_id)
                else None,
            }

        # 全量健康检查
        m0_summary = self._m0_manager.get_health_summary()
        triggers = self.list_all()
        by_type: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        for tr in triggers:
            by_type[tr.trigger_type] = by_type.get(tr.trigger_type, 0) + 1
            by_layer[tr.layer] = by_layer.get(tr.layer, 0) + 1
        return {
            "summary": m0_summary,
            "triggers": [t.to_dict() for t in triggers],
            "by_type": by_type,
            "by_layer": by_layer,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    # ── 推导 ──────────────────────────────────────

    def run_derivation(self) -> dict[str, Any]:
        """执行 Trigger 推导规则"""
        triggers = list(self._triggers.values())
        if not triggers:
            return {"error": "no triggers loaded"}

        # 从 M0 快照构建 context
        context = {}
        for tid, m0 in self._m0_manager.get_all_snapshots().items():
            context[f"failures_{tid}"] = m0.consecutive_failures
            context[f"duration_{tid}"] = m0.last_duration_seconds
            context[f"queue_{tid}"] = m0.metadata.get("queue_size", 0)

        # 执行推导
        results = self._derivation_engine.execute_trigger_rules(triggers, context)
        summary = {
            "total_rules": len(results),
            "triggered": sum(1 for r in results if r.triggered),
            "by_risk_level": {},
            "findings": [],
            "executed_at": datetime.now(UTC).isoformat(),
        }

        for r in results:
            if r.triggered:
                summary["by_risk_level"][r.risk_level] = summary["by_risk_level"].get(r.risk_level, 0) + 1
                summary["findings"].append(
                    {
                        "rule_id": r.rule_id,
                        "risk_level": r.risk_level,
                        "message": r.message,
                        "details": r.details,
                    }
                )

        return summary

    # ── 治理 (闭环驱动) ──────────────────────────

    def run_heal(self) -> dict[str, Any]:
        """执行 Trigger 自动修复 (闭环驱动)"""
        derivation = self.run_derivation()
        findings = derivation.get("findings", [])

        if not findings:
            return {"status": "ok", "message": "no issues found", "actions": []}

        # 直接传递 dict 列表给 DerivationEngine
        heal_actions = self._derivation_engine.execute_trigger_driven_heal_dict(findings)
        return {
            "status": "healed" if heal_actions else "manual_intervention_needed",
            "findings_count": len(findings),
            "heal_actions": heal_actions,
            "executed_at": datetime.now(UTC).isoformat(),
        }

    # ── 仪表板 ──────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        """生成 Trigger 统一仪表板"""
        triggers = self.list_all()
        m0_summary = self._m0_manager.get_health_summary()

        # 依赖拓扑
        dependency_graph = {}
        for t in triggers:
            if t.dependencies:
                dependency_graph[t.trigger_id] = t.dependencies

        # 健康趋势
        health_trend = {
            t.trigger_id: {
                "health_score": t.health_score,
                "status": t.m0_status,
                "trend": "improving"
                if t.consecutive_failures == 0
                else ("degrading" if t.consecutive_failures >= 3 else "stable"),
            }
            for t in triggers
        }

        by_type: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        for tr in triggers:
            by_type[tr.trigger_type] = by_type.get(tr.trigger_type, 0) + 1
            by_layer[tr.layer] = by_layer.get(tr.layer, 0) + 1

        return {
            "total_triggers": len(triggers),
            "by_type": by_type,
            "by_layer": by_layer,
            "m0_health": m0_summary,
            "dependency_graph": dependency_graph,
            "health_trend": health_trend,
            "triggers": [t.to_dict() for t in triggers],
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # ── M0 操作 ──────────────────────────────────

    def record_execution(
        self,
        trigger_id: str,
        success: bool,
        duration_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> TriggerRuntimeSnapshot | None:
        """记录一次 Trigger 执行 (M0 快照)"""
        if trigger_id not in self._triggers:
            return None
        snap = self._m0_manager.record_execution(trigger_id, success, duration_seconds, metadata)
        self._m0_manager.save()
        return snap

    def save_m0(self) -> bool:
        """保存 M0 快照"""
        return self._m0_manager.save()

    def detect_drift(self) -> list[dict[str, Any]]:
        """检测 M1↔M0 漂移"""
        triggers = list(self._triggers.values())
        return self._m0_manager.detect_drift(triggers)
