"""
model_driven.management.omo_bridge — OMO 桥接

将 model-driven 的管理能力与 OMO 治理体系连接：
- Phase 同步
- Task 自动创建
- Debt 自动注册
- Audit 自动记录
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class OMOEventType(Enum):
    """OMO 事件类型"""

    PHASE_CREATED = "phase_created"
    PHASE_UPDATED = "phase_updated"
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    DEBT_REGISTERED = "debt_registered"
    DEBT_RESOLVED = "debt_resolved"
    AUDIT_RECORDED = "audit_recorded"


@dataclass
class OMOEvent:
    """OMO 事件"""

    id: str
    event_type: str
    source: str = "model-driven"
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OMOBridge:
    """OMO 桥接器 — 将 model-driven 事件同步到 OMO 治理体系

    支持两种模式:
    1. 内存模式 (默认): 事件保留在内存中，通过 get_* 方法获取
    2. 文件模式: 直接写入 .omo/ 目录，与 omo CLI 互通
    """

    def __init__(self, omo_dir: str | None = None):
        self._events: list[OMOEvent] = []
        self._pending_debts: list[dict[str, Any]] = []
        self._pending_tasks: list[dict[str, Any]] = []
        self._audit_log: list[dict[str, Any]] = []

        # 文件模式: 自动检测或手动指定 .omo/ 目录
        if omo_dir:
            self._omo_dir = Path(omo_dir)
        else:
            # 尝试自动检测 workspace 的 .omo/ 目录
            ws = Path.home() / "Workspace"
            if (ws / ".omo").exists():
                self._omo_dir = ws / ".omo"
            else:
                self._omo_dir = None

        self._file_mode = self._omo_dir is not None and self._omo_dir.exists()

    def emit(self, event_type: str, payload: dict[str, Any]) -> OMOEvent:
        """发送 OMO 事件"""
        event = OMOEvent(
            id=f"OMO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            event_type=event_type,
            payload=payload,
        )
        self._events.append(event)
        return event

    def register_debt(
        self,
        title: str,
        description: str = "",
        severity: str = "medium",
        source: str = "model-driven",
    ) -> dict[str, Any]:
        """注册债务"""
        debt = {
            "id": f"DEBT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "title": title,
            "description": description,
            "severity": severity,
            "source": source,
            "status": "registered",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self._pending_debts.append(debt)
        self.emit(OMOEventType.DEBT_REGISTERED.value, debt)
        return debt

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "P2",
        assignee: str = "",
    ) -> dict[str, Any]:
        """创建任务"""
        task = {
            "id": f"TASK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "title": title,
            "description": description,
            "priority": priority,
            "assignee": assignee,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._pending_tasks.append(task)
        self.emit(OMOEventType.TASK_CREATED.value, task)
        return task

    def record_audit(
        self,
        action: str,
        entity_type: str = "",
        entity_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> OMOEvent:
        """记录审计"""
        return self.emit(OMOEventType.AUDIT_RECORDED.value, {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
        })

    def get_pending_debts(self) -> list[dict[str, Any]]:
        """获取待处理债务"""
        return self._pending_debts.copy()

    def get_pending_tasks(self) -> list[dict[str, Any]]:
        """获取待处理任务"""
        return self._pending_tasks.copy()

    def get_events(self, event_type: str | None = None) -> list[OMOEvent]:
        """获取事件"""
        if event_type:
            return [e for e in self._events if e.event_type == event_type]
        return self._events.copy()

    def get_stats(self) -> dict[str, Any]:
        """获取统计"""
        return {
            "total_events": len(self._events),
            "pending_debts": len(self._pending_debts),
            "pending_tasks": len(self._pending_tasks),
            "audit_records": len(self._audit_log),
            "file_mode": self._file_mode,
            "omo_dir": str(self._omo_dir) if self._omo_dir else None,
            "events_by_type": {
                et.value: len([e for e in self._events if e.event_type == et.value])
                for et in OMOEventType
            },
        }

    # ── 文件模式: 直接写入 .omo/ 目录 ──────────────

    def write_task_to_file(self, task: dict[str, Any]) -> bool:
        """将任务写入 .omo/tasks/ 目录"""
        if not self._file_mode or not self._omo_dir:
            return False

        tasks_dir = self._omo_dir / "tasks" / "active"
        tasks_dir.mkdir(parents=True, exist_ok=True)

        task_id = task.get("id", f"TASK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        file_path = tasks_dir / f"{task_id}.yaml"

        try:
            import yaml
            with open(file_path, "w") as f:
                yaml.dump({
                    "id": task_id,
                    "subject": task.get("title", ""),
                    "description": task.get("description", ""),
                    "status": "pending",
                    "priority": task.get("priority", "P2"),
                    "assignee": task.get("assignee", ""),
                    "source": "model-driven",
                    "created_at": task.get("created_at", datetime.now(timezone.utc).isoformat()),
                }, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception:
            return False

    def write_debt_to_file(self, debt: dict[str, Any]) -> bool:
        """将债务写入 .omo/debt/ 目录"""
        if not self._file_mode or not self._omo_dir:
            return False

        debt_dir = self._omo_dir / "debt"
        debt_dir.mkdir(parents=True, exist_ok=True)

        debt_id = debt.get("id", f"DEBT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        file_path = debt_dir / f"{debt_id}.yaml"

        try:
            import yaml
            with open(file_path, "w") as f:
                yaml.dump({
                    "id": debt_id,
                    "title": debt.get("title", ""),
                    "description": debt.get("description", ""),
                    "severity": debt.get("severity", "medium"),
                    "status": "registered",
                    "source": "model-driven",
                    "registered_at": debt.get("registered_at", datetime.now(timezone.utc).isoformat()),
                }, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception:
            return False

    def write_audit_to_log(self, action: str, entity_type: str = "", entity_id: str = "", details: dict[str, Any] | None = None) -> bool:
        """将审计记录写入 .omo/ 审计日志"""
        if not self._file_mode or not self._omo_dir:
            return False

        audit_entry = {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "source": "model-driven",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._audit_log.append(audit_entry)

        # 写入 JSONL 日志
        log_dir = self._omo_dir / "_knowledge"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "model-driven-audit.jsonl"

        try:
            import json
            with open(log_path, "a") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False

    def sync_phase(self, phase_id: str, status: str, details: dict[str, Any] | None = None) -> bool:
        """同步 Phase 状态到 .omo/state/system.yaml"""
        if not self._file_mode or not self._omo_dir:
            return False

        state_path = self._omo_dir / "state" / "system.yaml"
        if not state_path.exists():
            return False

        try:
            import yaml
            with open(state_path) as f:
                state = yaml.safe_load(f) or {}

            key = f"{phase_id}_status"
            state[key] = status
            if details:
                state[f"{phase_id}_details"] = details
            state["updated_at"] = datetime.now(timezone.utc).isoformat()

            with open(state_path, "w") as f:
                yaml.dump(state, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception:
            return False

    # ── 便捷方法: 自动选择内存/文件模式 ──────────────

    def register_debt_and_persist(
        self,
        title: str,
        description: str = "",
        severity: str = "medium",
    ) -> dict[str, Any]:
        """注册债务 (内存 + 文件双写)"""
        debt = self.register_debt(title, description, severity)
        if self._file_mode:
            self.write_debt_to_file(debt)
        return debt

    def create_task_and_persist(
        self,
        title: str,
        description: str = "",
        priority: str = "P2",
        assignee: str = "",
    ) -> dict[str, Any]:
        """创建任务 (内存 + 文件双写)"""
        task = self.create_task(title, description, priority, assignee)
        if self._file_mode:
            self.write_task_to_file(task)
        return task

    def record_audit_and_persist(
        self,
        action: str,
        entity_type: str = "",
        entity_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> OMOEvent:
        """记录审计 (内存 + 文件双写)"""
        event = self.record_audit(action, entity_type, entity_id, details)
        if self._file_mode:
            self.write_audit_to_log(action, entity_type, entity_id, details)
        return event

    # ── OMO 双向通道: 读取 OMO 状态 ──────────────────

    def read_omo_state(self) -> dict[str, Any]:
        """从 .omo/state/system.yaml 读取 OMO 系统状态"""
        if not self._file_mode or not self._omo_dir:
            return {"error": "file_mode not available"}

        state_path = self._omo_dir / "state" / "system.yaml"
        if not state_path.exists():
            return {"error": f"state file not found: {state_path}"}

        try:
            import yaml
            with open(state_path) as f:
                state = yaml.safe_load(f) or {}
            return {
                "success": True,
                "current_phase": state.get("current_phase", "unknown"),
                "health_score": state.get("health_score", 0),
                "active_tasks": state.get("active_tasks", 0),
                "completed_tasks": state.get("completed_tasks", 0),
                "total_tasks": state.get("total_tasks", 0),
                "blocked_tasks": state.get("blocked_tasks", 0),
                "active_agents": state.get("active_agents", 0),
                "debt_health": state.get("debt_metrics", {}).get("debt_health", 0) if isinstance(state.get("debt_metrics"), dict) else 0,
                "raw": state,
            }
        except Exception as e:
            return {"error": str(e)}

    def read_omo_tasks(self, status: str = "active") -> list[dict[str, Any]]:
        """从 .omo/tasks/ 读取任务列表"""
        if not self._file_mode or not self._omo_dir:
            return []

        tasks_dir = self._omo_dir / "tasks" / status
        if not tasks_dir.exists():
            return []

        tasks = []
        try:
            import yaml
            for f in sorted(tasks_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(open(f))
                    if data:
                        tasks.append(data)
                except Exception:
                    pass
        except Exception:
            pass

        return tasks

    def read_omo_debts(self) -> list[dict[str, Any]]:
        """从 .omo/debt/ 读取债务列表"""
        if not self._file_mode or not self._omo_dir:
            return []

        debt_dir = self._omo_dir / "debt"
        if not debt_dir.exists():
            return []

        debts = []
        try:
            import yaml
            for f in sorted(debt_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(open(f))
                    if data:
                        debts.append(data)
                except Exception:
                    pass
        except Exception:
            pass

        return debts

    def sync_pipeline_to_omo(self, pipeline_progress: dict[str, Any]) -> bool:
        """将 model-driven Pipeline 进度同步到 OMO 状态

        双向同步: model-driven PipelineTracker → .omo/state/system.yaml
        使用文件锁 (fcntl.flock) 保护并发写入。
        """
        if not self._file_mode or not self._omo_dir:
            return False

        state_path = self._omo_dir / "state" / "system.yaml"
        if not state_path.exists():
            return False

        try:
            import fcntl
            import yaml

            # 文件锁保护并发写入
            with open(state_path, "r+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.seek(0)
                state = yaml.safe_load(f) or {}

                # 写入 Pipeline 进度
                state["md_pipeline"] = {
                    "current_phase": pipeline_progress.get("current_phase", "unknown"),
                    "overall_progress": pipeline_progress.get("overall_progress", 0),
                    "phases": pipeline_progress.get("phases", {}),
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }
                state["updated_at"] = datetime.now(timezone.utc).isoformat()

                f.seek(0)
                f.truncate()
                yaml.dump(state, f, allow_unicode=True, default_flow_style=False)
                fcntl.flock(f, fcntl.LOCK_UN)
            return True
        except Exception:
            return False

    def get_omo_health_summary(self) -> dict[str, Any]:
        """获取 OMO 健康摘要 — 双向通道核心方法

        整合 model-driven 内部状态 + .omo/ 文件系统状态。
        """
        omo_state = self.read_omo_state()
        md_stats = self.get_stats()

        return {
            "omo": {
                "phase": omo_state.get("current_phase", "unknown") if omo_state.get("success") else "unavailable",
                "health_score": omo_state.get("health_score", 0),
                "tasks": f"{omo_state.get('completed_tasks', 0)}/{omo_state.get('total_tasks', 0)}",
                "debt_health": omo_state.get("debt_health", 0),
            },
            "model_driven": {
                "events": md_stats["total_events"],
                "pending_debts": md_stats["pending_debts"],
                "pending_tasks": md_stats["pending_tasks"],
                "file_mode": md_stats["file_mode"],
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
