"""
model_driven.mcp_server — MCP Server (统一工具链入口)

提供 model-driven 所有能力的 MCP 工具接口：
- 生命周期管理工具
- 模型驱动工具链
- 管理面工具
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MCPTool:
    """MCP 工具定义"""

    name: str
    description: str
    category: str = ""
    handler: callable | None = None


class MCPServer:
    """MCP Server — 工具注册和路由"""

    def __init__(self):
        self._tools: dict[str, MCPTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """注册默认工具"""
        from model_driven.lifecycle.stages import LifecycleTracker
        from model_driven.lifecycle.tracking import LifecycleManager
        from model_driven.toolchain import create_default_bus
        from model_driven.management.spec import SpecManager
        from model_driven.management.adr import ADRManager
        from model_driven.management.okr import OKRManager
        from model_driven.management.omo_bridge import OMOBridge
        from model_driven.management.agent_collab import AgentCollabManager
        from model_driven.ssot.lifecycle_ssot import (
            CrossStageConsistencyChecker,
            LifecycleSSOT,
            ValueSSOT,
        )

        # 生命周期管理工具
        self._lifecycle_manager = LifecycleManager()
        self._transition_engine = None  # lazy init

        # 模型驱动工具链
        self._toolchain_bus = create_default_bus()

        # 管理面
        self._spec_manager = SpecManager()
        self._adr_manager = ADRManager()
        self._okr_manager = OKRManager()
        self._omo_bridge = OMOBridge()
        self._agent_collab = AgentCollabManager()

        # SSOT
        self._lifecycle_ssot = LifecycleSSOT()
        self._value_ssot = ValueSSOT()
        self._cross_checker = CrossStageConsistencyChecker()

        # 注册工具
        self._register_tool("lifecycle-create", "创建实体的生命周期追踪器", "lifecycle",
                            self._handle_lifecycle_create)
        self._register_tool("lifecycle-advance", "推进实体到下一阶段", "lifecycle",
                            self._handle_lifecycle_advance)
        self._register_tool("lifecycle-status", "查询生命周期状态", "lifecycle",
                            self._handle_lifecycle_status)
        self._register_tool("lifecycle-dashboard", "生成全生命周期仪表板", "lifecycle",
                            self._handle_lifecycle_dashboard)
        self._register_tool("lifecycle-blockers", "获取所有阻塞项", "lifecycle",
                            self._handle_lifecycle_blockers)

        self._register_tool("spec-create", "创建 Spec", "spec",
                            self._handle_spec_create)
        self._register_tool("spec-list", "列出 Spec", "spec",
                            self._handle_spec_list)

        self._register_tool("adr-create", "创建 ADR", "adr",
                            self._handle_adr_create)
        self._register_tool("adr-list", "列出 ADR", "adr",
                            self._handle_adr_list)

        self._register_tool("okr-create", "创建 OKR", "okr",
                            self._handle_okr_create)
        self._register_tool("okr-progress", "查询 OKR 进度", "okr",
                            self._handle_okr_progress)

        self._register_tool("debt-register", "注册债务", "omo",
                            self._handle_debt_register)
        self._register_tool("task-create", "创建任务", "omo",
                            self._handle_task_create)
        self._register_tool("audit-record", "记录审计", "omo",
                            self._handle_audit_record)

        self._register_tool("collab-create", "创建协作任务", "collab",
                            self._handle_collab_create)
        self._register_tool("collab-assign", "分配协作任务", "collab",
                            self._handle_collab_assign)
        self._register_tool("collab-status", "查询协作状态", "collab",
                            self._handle_collab_status)

        self._register_tool("model-execute", "执行模型驱动工具", "toolchain",
                            self._handle_model_execute)
        self._register_tool("model-tools", "列出可用模型工具", "toolchain",
                            self._handle_model_tools)

        self._register_tool("ssot-drift-check", "检查 SSOT 漂移", "ssot",
                            self._handle_ssot_drift_check)
        self._register_tool("cross-stage-check", "跨阶段一致性检查", "ssot",
                            self._handle_cross_stage_check)
        self._register_tool("value-roi", "计算 ROI", "ssot",
                            self._handle_value_roi)

        # Trigger 工具
        self._register_tool("trigger-list", "列出所有 Trigger (支持按类型/层过滤)", "trigger",
                            self._handle_trigger_list)
        self._register_tool("trigger-status", "检查 Trigger 健康状态 (M1+M0)", "trigger",
                            self._handle_trigger_status)
        self._register_tool("trigger-derive", "执行 Trigger 推导规则", "trigger",
                            self._handle_trigger_derive)
        self._register_tool("trigger-heal", "执行 Trigger 自动修复", "trigger",
                            self._handle_trigger_heal)
        self._register_tool("trigger-dashboard", "Trigger 统一仪表板", "trigger",
                            self._handle_trigger_dashboard)
        self._register_tool("trigger-drift", "检测 Trigger M1↔M0 漂移", "trigger",
                            self._handle_trigger_drift)

    def _register_tool(self, name: str, description: str, category: str, handler: callable) -> None:
        self._tools[name] = MCPTool(name=name, description=description, category=category, handler=handler)

    def list_tools(self, category: str | None = None) -> list[dict[str, Any]]:
        """列出工具"""
        tools = []
        for tool in self._tools.values():
            if category and tool.category != category:
                continue
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
            })
        return tools

    def execute(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """执行工具"""
        tool = self._tools.get(tool_name)
        if not tool or not tool.handler:
            return {"success": False, "error": f"工具不存在: {tool_name}"}
        try:
            return tool.handler(**kwargs)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Handlers ──

    def _handle_lifecycle_create(self, entity_id: str, entity_type: str = "", **kwargs) -> dict:
        tracker = self._lifecycle_manager.create_tracker(entity_id, entity_type)
        return {"success": True, "entity_id": entity_id, "message": "生命周期追踪器已创建"}

    def _handle_lifecycle_advance(self, entity_id: str, target_stage: str, **kwargs) -> dict:
        from model_driven.mof.m3_extended import LifecycleStage
        from model_driven.lifecycle.transitions import TransitionEngine

        tracker = self._lifecycle_manager.get_tracker(entity_id)
        if not tracker:
            return {"success": False, "error": f"实体不存在: {entity_id}"}

        try:
            target = LifecycleStage.from_str(target_stage)
        except ValueError:
            return {"success": False, "error": f"无效阶段: {target_stage}"}

        if not self._transition_engine:
            self._transition_engine = TransitionEngine()

        success, msg, _ = self._transition_engine.try_transition(tracker, target, kwargs)
        return {"success": success, "message": msg, "current_stage": tracker.current_stage.value if tracker.current_stage else None}

    def _handle_lifecycle_status(self, entity_id: str, **kwargs) -> dict:
        summary = self._lifecycle_manager.get_stage_summary(entity_id)
        if not summary:
            return {"success": False, "error": f"实体不存在: {entity_id}"}
        return {"success": True, "summary": summary}

    def _handle_lifecycle_dashboard(self, **kwargs) -> dict:
        dashboard = self._lifecycle_manager.generate_dashboard()
        return {"success": True, "dashboard": {
            "total_entities": dashboard.total_entities,
            "by_stage": dashboard.entities_by_stage,
            "blockers": dashboard.blockers,
            "avg_progress": dashboard.avg_progress,
        }}

    def _handle_lifecycle_blockers(self, **kwargs) -> dict:
        blockers = self._lifecycle_manager.get_all_blockers()
        return {"success": True, "blockers": blockers, "count": len(blockers)}

    def _handle_spec_create(self, spec_id: str, title: str, **kwargs) -> dict:
        spec = self._spec_manager.create(spec_id, title, **kwargs)
        return {"success": True, "spec_id": spec.id, "status": spec.status.value}

    def _handle_spec_list(self, status: str = "", **kwargs) -> dict:
        if status:
            from model_driven.management.spec import SpecStatus
            try:
                st = SpecStatus(status)
                specs = self._spec_manager.list_by_status(st)
            except ValueError:
                specs = []
        else:
            specs = self._spec_manager.list_all()
        return {"success": True, "specs": [{"id": s.id, "title": s.title, "status": s.status.value} for s in specs]}

    def _handle_adr_create(self, adr_id: str, title: str, **kwargs) -> dict:
        adr = self._adr_manager.create(adr_id, title, **kwargs)
        return {"success": True, "adr_id": adr.id, "status": adr.status.value}

    def _handle_adr_list(self, **kwargs) -> dict:
        adrs = self._adr_manager.list_all()
        return {"success": True, "adrs": [{"id": a.id, "title": a.title, "status": a.status.value} for a in adrs]}

    def _handle_okr_create(self, okr_id: str, objective: str, **kwargs) -> dict:
        okr = self._okr_manager.create(okr_id, objective, **kwargs)
        return {"success": True, "okr_id": okr.id, "status": okr.status.value}

    def _handle_okr_progress(self, okr_id: str = "", **kwargs) -> dict:
        if okr_id:
            okr = self._okr_manager.get(okr_id)
            if not okr:
                return {"success": False, "error": f"OKR 不存在: {okr_id}"}
            return {"success": True, "okr_id": okr_id, "progress": okr.progress}
        stats = self._okr_manager.get_stats()
        return {"success": True, "stats": stats}

    def _handle_debt_register(self, title: str, description: str = "", severity: str = "medium", **kwargs) -> dict:
        debt = self._omo_bridge.register_debt(title, description, severity)
        return {"success": True, "debt": debt}

    def _handle_task_create(self, title: str, description: str = "", priority: str = "P2", **kwargs) -> dict:
        task = self._omo_bridge.create_task(title, description, priority)
        return {"success": True, "task": task}

    def _handle_audit_record(self, action: str, entity_type: str = "", entity_id: str = "", **kwargs) -> dict:
        self._omo_bridge.record_audit(action, entity_type, entity_id, kwargs.get("details"))
        return {"success": True, "message": "审计已记录"}

    def _handle_collab_create(self, task_id: str, title: str, assigned_by: str = "", **kwargs) -> dict:
        task = self._agent_collab.create_task(task_id, title, assigned_by, **kwargs)
        return {"success": True, "task_id": task.id, "status": task.status.value}

    def _handle_collab_assign(self, task_id: str, agent_name: str, **kwargs) -> dict:
        success = self._agent_collab.assign_task(task_id, agent_name)
        return {"success": success, "task_id": task_id, "agent": agent_name}

    def _handle_collab_status(self, **kwargs) -> dict:
        stats = self._agent_collab.get_stats()
        conflicts = self._agent_collab.detect_conflicts()
        return {"success": True, "stats": stats, "conflicts": conflicts}

    def _handle_model_execute(self, tool: str, **kwargs) -> dict:
        result = self._toolchain_bus.execute(tool, **kwargs)
        return {"success": result.success, "message": result.message, "data": result.data}

    def _handle_model_tools(self, category: str = "", **kwargs) -> dict:
        tools = self._toolchain_bus.list_tools(category or None)
        return {"success": True, "tools": [{"name": t.name, "description": t.description, "category": t.category} for t in tools]}

    def _handle_ssot_drift_check(self, entity_id: str, **kwargs) -> dict:
        current = self._lifecycle_ssot.get_current_state(entity_id)
        if not current:
            return {"success": False, "error": f"无快照数据: {entity_id}"}
        drifts = self._lifecycle_ssot.detect_drift(entity_id, kwargs.get("declared_state", {}))
        return {"success": True, "drifts": drifts, "has_drift": len(drifts) > 0}

    def _handle_cross_stage_check(self, **kwargs) -> dict:
        result = self._cross_checker.check(
            kwargs.get("planning", []),
            kwargs.get("design", []),
            kwargs.get("dev", []),
            kwargs.get("deploy", []),
            kwargs.get("runtime", []),
        )
        return {"success": True, "result": result}

    def _handle_value_roi(self, entity_id: str, **kwargs) -> dict:
        roi = self._value_ssot.calculate_roi(entity_id)
        return {"success": True, "roi": roi}

    # ── Trigger 工具 ──────────────────────────────

    def _handle_trigger_list(self, trigger_type: str = "", layer: str = "", **kwargs) -> dict:
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry()
        triggers = registry.list_all(
            trigger_type=trigger_type or None,
            layer=layer or None,
        )
        return {
            "success": True,
            "total": len(triggers),
            "triggers": [t.to_dict() for t in triggers],
            "types": registry.list_types(),
            "layers": registry.list_layers(),
        }

    def _handle_trigger_status(self, trigger_id: str = "", **kwargs) -> dict:
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry()
        return registry.check_health(trigger_id or None)

    def _handle_trigger_derive(self, **kwargs) -> dict:
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry()
        return {"success": True, "derivation": registry.run_derivation()}

    def _handle_trigger_heal(self, **kwargs) -> dict:
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry()
        return {"success": True, "heal": registry.run_heal()}

    def _handle_trigger_dashboard(self, **kwargs) -> dict:
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry()
        return {"success": True, "dashboard": registry.get_dashboard()}

    def _handle_trigger_drift(self, **kwargs) -> dict:
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry()
        drifts = registry.detect_drift()
        return {"success": True, "drifts": drifts, "has_drift": len(drifts) > 0}
