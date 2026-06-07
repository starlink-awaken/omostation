"""Layer 2: 拓扑发现层 — 算力节点发现与网络分区。

核心类型:
  - :class:`ComputeNode`: 算力节点描述
  - :class:`NodeStatus`: 节点状态枚举
  - :class:`NodeEngineType`: 引擎类型枚举
  - :class:`NodeRegistry`: 线程安全节点注册表
  - :class:`TopologyScanner`: 多后端发现编排器

快速开始::

    from compute_mesh.topology import TopologyScanner, NodeRegistry

    registry = NodeRegistry()
    scanner = TopologyScanner(registry)
    nodes = scanner.scan_all()
    print(f"Discovered {len(nodes)} compute nodes")
"""

from .node import ComputeNode, NodeEngineType, NodeStatus
from .registry import NodeRegistry
from .scanner import (
    CLOUD_PROVIDERS,
    LOCAL_DAEMONS,
    TopologyScanner,
    detect_cloud_nodes,
    load_static_nodes,
    probe_local_daemons,
)

__all__ = (
    "CLOUD_PROVIDERS",
    "ComputeNode",
    "LOCAL_DAEMONS",
    "NodeEngineType",
    "NodeRegistry",
    "NodeStatus",
    "TopologyScanner",
    "detect_cloud_nodes",
    "load_static_nodes",
    "probe_local_daemons",
)
