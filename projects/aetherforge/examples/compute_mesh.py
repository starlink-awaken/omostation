"""Example 2: 算力网格 — 发现节点 + 自动路由到最优节点。"""

from compute_mesh.pool import ComputePool

# 1. 创建算力池并自动发现节点
pool = ComputePool()
pool.scan()

print("=" * 50)
print("🔮 算力节点全景")
print("=" * 50)

# 2. 健康检查
results = pool.health_check_all()
online = sum(1 for v in results.values() if v)
print(f"\n{online}/{pool.node_count} 节点在线")

# 3. 列出所有节点
for node in pool.registry.get_all():
    icon = "🟢" if node.is_online else "🔴"
    print(f"  {icon} {node.node_id:30s} {node.engine_type.value:12s} zone={node.network_zone}")

# 4. 选择最优节点
best = pool.get_best_node()
if best:
    print(f"\n⚡ 最优节点: {best.node_id}")
    print(f"   类型: {best.engine_type.value}")
    print(f"   区域: {best.network_zone}")
    print(f"   负载: {best.load_factor:.1%}")
