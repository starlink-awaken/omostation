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

from ecos.common.logger import get_logger

logger = get_logger("task_scheduler")


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
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class TaskScheduler:
    """分布式任务调度器

    管理分布式系统中的任务分配、执行和完成
    支持可选的持久化存储和配置管理
    """

    def __init__(self, persistence=None, config=None):
        from ecos.common.config import ECOSConfig

        self.config = config or ECOSConfig.get_instance()
        self.tasks: dict[str, TaskInfo] = {}
        self.task_queue: list[str] = []
        self._persistence = persistence
        self.max_tasks = self.config.get("task_scheduler.max_tasks", 1000)
        self.task_timeout = self.config.get("task_scheduler.timeout", 300)
        if persistence:
            self._load_state()

    def _load_state(self):
        """从持久化加载状态"""
        try:
            saved = self._persistence.load("task_scheduler")
            if saved and "tasks" in saved:
                for task_id, task_data in saved["tasks"].items():
                    task = TaskInfo(
                        task_id=task_data.get("task_id", task_id),
                        name=task_data.get("name", ""),
                        description=task_data.get("description", ""),
                        required_capabilities=task_data.get(
                            "required_capabilities", []
                        ),
                        status=TaskStatus(task_data.get("status", "pending")),
                        assigned_agent=task_data.get("assigned_agent", ""),
                        priority=task_data.get("priority", 0),
                    )
                    self.tasks[task_id] = task
                self.task_queue = saved.get("queue", [])
                logger.info("从持久化加载任务: %d 个", len(self.tasks))
        except Exception as e:  # defensive fallback
            logger.error("加载状态失败: %s", str(e))

    def _save_state(self):
        """保存状态到持久化"""
        if self._persistence:
            try:
                state = {
                    "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
                    "queue": self.task_queue,
                }
                self._persistence.save("task_scheduler", state)
                logger.debug("保存任务状态: %d 个", len(self.tasks))
            except Exception as e:  # defensive fallback
                logger.error("保存状态失败: %s", str(e))

    def submit_task(
        self,
        task_id: str,
        name: str,
        description: str = "",
        required_capabilities: list[str] | None = None,
        priority: int = 0,
    ) -> TaskInfo:
        """提交任务"""
        try:
            if task_id in self.tasks:
                logger.warning("任务已存在: %s", task_id)
                return self.tasks[task_id]

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
            logger.info("提交任务: %s, name=%s, priority=%d", task_id, name, priority)
            self._save_state()
            return task
        except Exception as e:  # defensive fallback
            logger.error("提交任务失败: %s - %s", task_id, str(e))
            raise

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

        self._save_state()
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
        return [
            self.tasks[tid]
            for tid in self.task_queue
            if self.tasks[tid].status == TaskStatus.PENDING
        ]

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
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "queue": self.task_queue,
        }


class DAGScheduler:
    """DAG 任务调度器 — 拓扑排序 + 就绪检测 + 并行调度"""

    def __init__(self, task_scheduler: TaskScheduler):
        self._scheduler = task_scheduler
        self._dependencies: dict[str, set[str]] = {}
        self._dependents: dict[str, set[str]] = {}
        self._completed: set[str] = set()

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """添加依赖: task_id 依赖 depends_on"""
        self._dependencies.setdefault(task_id, set()).add(depends_on)
        self._dependents.setdefault(depends_on, set()).add(task_id)

    def get_ready_tasks(self) -> list[str]:
        """获取就绪任务（所有依赖已完成）"""
        ready = []
        for task_id in self._scheduler.task_queue:
            task = self._scheduler.get_task(task_id)
            if not task or task.status != TaskStatus.PENDING:
                continue

            deps = self._dependencies.get(task_id, set())
            if deps.issubset(self._completed):
                ready.append(task_id)
        return ready

    def mark_completed(self, task_id: str) -> list[str]:
        """标记任务完成，返回新就绪的任务"""
        self._completed.add(task_id)
        new_ready = []
        for dependent in self._dependents.get(task_id, set()):
            dep_task = self._scheduler.get_task(dependent)
            if dep_task and dep_task.status == TaskStatus.PENDING:
                deps = self._dependencies.get(dependent, set())
                if deps.issubset(self._completed):
                    new_ready.append(dependent)
        return new_ready

    def get_topological_order(self) -> list[str]:
        """拓扑排序"""
        in_degree: dict[str, int] = {}
        all_tasks = set(self._scheduler.tasks.keys())

        for task_id in all_tasks:
            in_degree[task_id] = len(self._dependencies.get(task_id, set()))

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            queue.sort(key=lambda t: self._scheduler.tasks[t].priority, reverse=True)
            current = queue.pop(0)
            order.append(current)

            for dependent in self._dependents.get(current, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return order

    def get_execution_plan(self) -> list[list[str]]:
        """生成并行执行计划（每层可并行）"""
        order = self.get_topological_order()
        if not order:
            return []

        levels: list[list[str]] = []
        remaining = set(order)

        while remaining:
            level = []
            for task_id in order:
                if task_id not in remaining:
                    continue
                deps = self._dependencies.get(task_id, set())
                if deps.issubset(self._completed | set(sum(levels, []))):
                    level.append(task_id)

            if not level:
                break

            levels.append(level)
            remaining -= set(level)

        return levels

    def get_critical_path(self) -> list[str]:
        """获取关键路径（最长依赖链）"""
        order = self.get_topological_order()
        if not order:
            return []

        dist: dict[str, int] = {tid: 0 for tid in order}
        pred: dict[str, Optional[str]] = {tid: None for tid in order}

        for task_id in order:
            for dependent in self._dependents.get(task_id, set()):
                if dependent in dist:
                    new_dist = dist[task_id] + 1
                    if new_dist > dist[dependent]:
                        dist[dependent] = new_dist
                        pred[dependent] = task_id

        if not dist:
            return []

        end = max(dist, key=lambda k: dist[k])
        path = []
        current: Optional[str] = end
        while current is not None:
            path.append(current)
            current = pred.get(current)
        path.reverse()
        return path

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_tasks": len(self._scheduler.tasks),
            "completed": len(self._completed),
            "dependencies": sum(len(v) for v in self._dependencies.values()),
            "ready_tasks": len(self.get_ready_tasks()),
        }
