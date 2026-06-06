"""Task Scheduler — 异步任务调度与生命周期管理。

基于 asyncio 的轻量级任务队列，支持优先级调度、并发控制、状态跟踪和取消操作。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

log = logging.getLogger(__name__)


class TaskStatus(StrEnum):
    """任务状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskDef:
    """任务定义。"""

    agent_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # Runtime state (managed by TaskScheduler)
    status: TaskStatus = field(default=TaskStatus.PENDING, init=False)
    result: Any = field(default=None, init=False)
    error: str | None = field(default=None, init=False)


TaskExecutor = Callable[[TaskDef], Awaitable[Any]]


class TaskScheduler:
    """异步任务调度器。

    维护一个优先级队列，后台 worker 按优先级消费任务并执行。
    支持并发控制、状态查询和取消操作。

    Usage::

        scheduler = TaskScheduler(max_concurrent=3)
        scheduler.set_executor(my_async_fn)
        await scheduler.start()
        task_id = await scheduler.schedule(TaskDef(...))
        await scheduler.stop()
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        self._tasks: dict[str, TaskDef] = {}
        self._queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
        self._executor: TaskExecutor | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._seq = 0

    def set_executor(self, executor: TaskExecutor) -> None:
        """设置任务执行器（接收 TaskDef 的异步可调用对象）。"""
        self._executor = executor

    async def start(self) -> None:
        """启动后台 worker 协程。幂等。"""
        if self._worker_task is not None:
            return
        self._worker_task = asyncio.create_task(self._worker_loop())
        log.debug("TaskScheduler worker started")

    async def stop(self) -> None:
        """停止调度器，将所有 PENDING 任务标为 CANCELLED。"""
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        self._worker_task = None
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
        log.debug("TaskScheduler stopped")

    async def schedule(self, task: TaskDef) -> str:
        """调度一个任务进入队列，返回 task_id。

        Raises:
            RuntimeError: 若 executor 未设置或调度器未启动。
        """
        if self._executor is None:
            raise RuntimeError("TaskScheduler executor not set. Call set_executor() first.")
        if self._worker_task is None:
            raise RuntimeError("TaskScheduler not started. Call start() first.")

        if not task.id:
            task.id = uuid.uuid4().hex[:12]
        task.status = TaskStatus.PENDING
        self._tasks[task.id] = task
        self._seq += 1
        await self._queue.put((-task.priority, self._seq, task.id))
        log.debug("Task %s scheduled (action=%s)", task.id, task.action)
        return task.id

    def get_status(self, task_id: str) -> TaskStatus:
        """查询任务状态。

        Raises:
            KeyError: 若任务 ID 不存在。
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        return task.status

    def cancel(self, task_id: str) -> bool:
        """取消任务。可取消 PENDING 或 RUNNING 状态的任务。

        Returns:
            True 若成功取消，False 若不存在或已处于终态。
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            task.status = TaskStatus.CANCELLED
            return True
        return False

    async def _worker_loop(self) -> None:
        """后台 worker：从优先级队列取任务，通过 semaphore 控制并发。"""
        while True:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                while not self._queue.empty():
                    self._queue.get_nowait()
                raise

            _, _, task_id = item
            task = self._tasks.get(task_id)
            if task is None or task.status == TaskStatus.CANCELLED:
                self._queue.task_done()
                continue

            async with self._semaphore:
                task.status = TaskStatus.RUNNING
                log.debug("Task %s running (action=%s)", task_id, task.action)
                assert self._executor is not None
                try:
                    task.result = await self._executor(task)
                    if task.status != TaskStatus.CANCELLED:
                        task.status = TaskStatus.COMPLETED
                except asyncio.CancelledError:
                    task.status = TaskStatus.CANCELLED
                except Exception as exc:
                    task.error = str(exc)
                    if task.status != TaskStatus.CANCELLED:
                        task.status = TaskStatus.FAILED
                    log.warning("Task %s failed: %s", task_id, exc)
                finally:
                    self._queue.task_done()
