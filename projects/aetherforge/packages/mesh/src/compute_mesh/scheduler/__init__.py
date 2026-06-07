"""Layer 4: 调度扩展层 — Mesh-aware 策略路由。

核心类型:
  - :class:`MeshScheduler`: 封装 gateway 的 ModelScheduler，增加拓扑感知

快速开始::

    from compute_mesh.scheduler import MeshScheduler
    from compute_mesh.pool import ComputePool
    from llm_gateway.scheduler import ModelScheduler as GatewayScheduler

    pool = ComputePool()
    pool.scan()
    pool.health_check_all()

    gateway = GatewayScheduler(registry)
    mesh_sched = MeshScheduler(pool, gateway)
"""

from .mesh_scheduler import MeshScheduler

__all__ = ("MeshScheduler",)
