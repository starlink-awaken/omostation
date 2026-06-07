"""Layer 3: 算力资源池 — 成本核算/健康监控/负载追踪/配额管理。

核心类型:
  - :class:`ComputePool`: 资源聚合、健康检查、负载管理
  - :class:`CostTracker`: 成本记录与报告

快速开始::

    from compute_mesh.pool import ComputePool, CostTracker
    from compute_mesh.topology import NodeRegistry

    registry = NodeRegistry()
    pool = ComputePool(registry)
    pool.scan()
    pool.health_check_all()

    tracker = CostTracker(registry)
    tracker.record("ollama-local", prompt_tokens=100, completion_tokens=50)
    print(tracker.get_report())
"""

from .cost import CostTracker
from .manager import ComputePool

__all__ = (
    "ComputePool",
    "CostTracker",
)
