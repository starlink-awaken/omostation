# 算力网格 (Mesh)

Mesh 自动发现、管理、路由你的所有算力资源。

## 核心概念

- **ComputeNode**: 算力节点 (Ollama/OpenAI/远程机器)
- **TopologyLabels**: 四层拓扑 (region/zone/rack/host)
- **ComputePool**: 资源池 (健康/负载/成本)
- **MeshWorker**: 执行槽位
- **ObjectStore**: 对象存储

## CLI 用法

```bash
aetherforge mesh list              # 列出所有节点
aetherforge mesh status            # 健康状态
aetherforge mesh health            # 批量健康检查
aetherforge mesh topology-scan     # 重新发现
aetherforge mesh generate "你好"   # 自动路由最优节点
aetherforge mesh cost              # 成本报告
aetherforge mesh worker-list       # 列出 Worker
```

## Python 用法

```python
from compute_mesh.pool import ComputePool

pool = ComputePool()
pool.scan()                          # 发现节点
pool.health_check_all()              # 健康检查
best = pool.get_best_node()          # 最优节点
print(f"最优: {best.node_id}")

# 四层拓扑
from compute_mesh.topology import ComputeNode, TopologyLabels
node = ComputeNode(
    node_id="ollama-prod",
    topology=TopologyLabels(region="cn-beijing", zone="cn-beijing-1a"),
)
```
