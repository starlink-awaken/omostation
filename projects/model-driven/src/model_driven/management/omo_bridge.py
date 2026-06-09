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
    """OMO 桥接器 — 将 model-driven 事件同步到 OMO 治理体系"""

    def __init__(self):
        self._events: list[OMOEvent] = []
        self._pending_debts: list[dict[str, Any]] = []
        self._pending_tasks: list[dict[str, Any]] = []

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
            "events_by_type": {
                et.value: len([e for e in self._events if e.event_type == et.value])
                for et in OMOEventType
            },
        }
