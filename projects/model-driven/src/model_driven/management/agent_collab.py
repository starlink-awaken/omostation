"""
model_driven.management.agent_collab — 多 Agent 协作

提供多 Agent 协作的模型层支持：
- 协作任务创建/分配
- 协作状态追踪
- 冲突检测
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class CollabTaskStatus(Enum):
    """协作任务状态"""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CollabTask:
    """协作任务"""

    id: str
    title: str
    description: str = ""
    status: CollabTaskStatus = CollabTaskStatus.PENDING
    assigned_to: str = ""  # agent name
    assigned_by: str = ""  # agent name
    priority: str = "P2"  # P0-P3
    dependencies: list[str] = field(default_factory=list)  # 依赖的任务 ID
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = ""
    completed_at: str = ""


class AgentCollabManager:
    """多 Agent 协作管理器"""

    def __init__(self):
        self._tasks: dict[str, CollabTask] = {}
        self._agent_tasks: dict[str, list[str]] = {}  # agent → task_ids

    def create_task(
        self,
        task_id: str,
        title: str,
        assigned_by: str = "",
        **kwargs,
    ) -> CollabTask:
        """创建协作任务"""
        task = CollabTask(id=task_id, title=title, assigned_by=assigned_by, **kwargs)
        self._tasks[task_id] = task
        return task

    def assign_task(self, task_id: str, agent_name: str) -> bool:
        """分配任务给 Agent"""
        task = self._tasks.get(task_id)
        if task and task.status == CollabTaskStatus.PENDING:
            task.status = CollabTaskStatus.ASSIGNED
            task.assigned_to = agent_name
            task.updated_at = datetime.now(UTC).isoformat()
            if agent_name not in self._agent_tasks:
                self._agent_tasks[agent_name] = []
            self._agent_tasks[agent_name].append(task_id)
            return True
        return False

    def start_task(self, task_id: str) -> bool:
        """开始任务"""
        task = self._tasks.get(task_id)
        if task and task.status == CollabTaskStatus.ASSIGNED:
            # 检查依赖
            for dep_id in task.dependencies:
                dep = self._tasks.get(dep_id)
                if dep and dep.status != CollabTaskStatus.COMPLETED:
                    return False
            task.status = CollabTaskStatus.IN_PROGRESS
            task.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def complete_task(self, task_id: str) -> bool:
        """完成任务"""
        task = self._tasks.get(task_id)
        if task and task.status == CollabTaskStatus.IN_PROGRESS:
            task.status = CollabTaskStatus.COMPLETED
            task.completed_at = datetime.now(UTC).isoformat()
            task.updated_at = task.completed_at
            return True
        return False

    def block_task(self, task_id: str, reason: str) -> bool:
        """阻塞任务"""
        task = self._tasks.get(task_id)
        if task and task.status == CollabTaskStatus.IN_PROGRESS:
            task.status = CollabTaskStatus.BLOCKED
            task.context["block_reason"] = reason
            task.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def get_agent_tasks(self, agent_name: str) -> list[CollabTask]:
        """获取 Agent 的任务列表"""
        task_ids = self._agent_tasks.get(agent_name, [])
        return [self._tasks[tid] for tid in task_ids if tid in self._tasks]

    def get_stats(self) -> dict[str, Any]:
        """获取统计"""
        stats = {s.value: 0 for s in CollabTaskStatus}
        for task in self._tasks.values():
            stats[task.status.value] += 1
        stats["total"] = len(self._tasks)
        stats["agents"] = len(self._agent_tasks)
        return stats

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """检测协作冲突"""
        conflicts = []
        # 检测同一 Agent 的阻塞任务
        for agent_name, task_ids in self._agent_tasks.items():
            blocked = [
                tid for tid in task_ids if tid in self._tasks and self._tasks[tid].status == CollabTaskStatus.BLOCKED
            ]
            if blocked:
                conflicts.append(
                    {
                        "type": "agent_blocked",
                        "agent": agent_name,
                        "blocked_tasks": blocked,
                    }
                )
        return conflicts
