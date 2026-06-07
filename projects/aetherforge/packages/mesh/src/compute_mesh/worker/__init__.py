"""Layer 5: Worker 管理 — 注册/心跳/任务分发/结果聚合。

核心类型:
  - :class:`MeshWorker`: 执行槽位描述
  - :class:`WorkerStatus`: 工作状态枚举
  - :class:`WorkerRegistry`: 线程安全 Worker 注册表
  - :class:`TaskDispatcher`: 任务分发引擎

快速开始::

    from compute_mesh.worker import WorkerRegistry, TaskDispatcher
    from compute_mesh.pool import ComputePool

    pool = ComputePool()
    pool.scan()
    pool.health_check_all()

    registry = WorkerRegistry()
    dispatcher = TaskDispatcher(pool, registry)
    dispatcher.provision_all()  # 自动为在线节点创建 Worker

    result = dispatcher.dispatch("ollama-local", prompt="你好")
    print(result["content"])
"""

from .dispatcher import TaskDispatcher
from .registry import WorkerRegistry
from .worker import MeshWorker, WorkerStatus

__all__ = (
    "MeshWorker",
    "TaskDispatcher",
    "WorkerRegistry",
    "WorkerStatus",
)
