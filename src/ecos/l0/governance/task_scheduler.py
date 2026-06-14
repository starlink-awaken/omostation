"""L0 分布式原语 — 分布式任务调度器

实现多机协作的核心组件：
- TaskScheduler: 分布式任务调度
- TaskInfo: 任务信息
- TaskStatus: 任务状态枚举
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    name: str
    description: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: str = ""
    priority: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "required_capabilities": self.required_capabilities,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskScheduler:
    """分布式任务调度器
    
    管理分布式系统中的任务分配、执行和完成
    """
    
    def __init__(self):
        self.tasks: dict[str, TaskInfo] = {}
        self.task_queue: list[str] = []
    
    def submit_task(self, task_id: str, name: str, description: str = "",
                    required_capabilities: list[str] | None = None,
                    priority: int = 0) -> TaskInfo:
        """提交任务"""
        task = TaskInfo(
            task_id=task_id,
            name=name,
            description=description,
            required_capabilities=required_capabilities or [],
            priority=priority,
        )
        self.tasks[task_id] = task
        self.task_queue.append(task_id)
        self.task_queue.sort(key=lambda t: self.tasks[t].priority, reverse=True)
        return task
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """分配任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status != TaskStatus.PENDING:
            return False
        
        task.status = TaskStatus.ASSIGNED
        task.assigned_agent = agent_id
        return True
    
    def start_task(self, task_id: str) -> bool:
        """开始任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status != TaskStatus.ASSIGNED:
            return False
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        return True
    
    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """完成任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status != TaskStatus.RUNNING:
            return False
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        task.result = result
        
        # 从队列中移除
        if task_id in self.task_queue:
            self.task_queue.remove(task_id)
        
        return True
    
    def fail_task(self, task_id: str) -> bool:
        """任务失败"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        return True
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
            task.status = TaskStatus.CANCELLED
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)
            return True
        return False
    
    def get_task(self, task_id: str) -> TaskInfo | None:
        """获取任务信息"""
        return self.tasks.get(task_id)
    
    def get_pending_tasks(self) -> list[TaskInfo]:
        """获取待处理任务"""
        return [self.tasks[tid] for tid in self.task_queue if self.tasks[tid].status == TaskStatus.PENDING]
    
    def get_next_task(self) -> TaskInfo | None:
        """获取下一个任务"""
        for task_id in self.task_queue:
            task = self.tasks[task_id]
            if task.status == TaskStatus.PENDING:
                return task
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "tasks": {
                tid: t.to_dict()
                for tid, t in self.tasks.items()
            },
            "queue": self.task_queue,
        }
