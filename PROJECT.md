# Project: eCOS Architecture Convergence (eCOS 架构收敛与整合)

## Architecture
本项目的目标是对 eCOS 架构进行全局收敛与深度整合。具体包含：
1. **L0-I0 RPC 重构**：ECOS 工作流层（L0）与 AetherForge Swarm（I0）交互由原 subprocess.run 直调命令行改为 Agora MCP（I0）服务网格的 BOS URI（`bos://capability/swarm/run`）形式的统一 RPC 调用，由 Agora 代理路由分发。
2. **Swarm 事件与总线替换**：蜂群多智能体（Swarm）中，下线本地 `event_bus.py`，所有的智能体间广播、感知以及生命周期通知事件由系统统一的 `bus-foundation` 模块分发承载。
3. **Mesh-Omo 稳态自适应反馈闭环**：算力网格层（Mesh）检测到节点或 zone 的变更，发布 `bus-foundation` 事件；上层 Omo 治理引擎监听该事件，按照 L0 约束在 POSIX 锁与审计保障下将变更原子地写回 `.omo/state/system.yaml` 及对应的 M1 静态元 YAML 配置文件中。

## Milestones
详细的执行计划与进度见相对路径：
- 计划文档：[.agents/orchestrator/plan.md](.agents/orchestrator/plan.md)
- 进度记录：[.agents/orchestrator/progress.md](.agents/orchestrator/progress.md)

| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1 | Agora I0 MCP 跨层通信重构 | 将 ECOS workflow 的 Swarm backend 重构为 Agora BOS RPC 路由，注册 `bos://capability/swarm/run` | 调研完成 | PLANNED |
| M2 | Swarm 底层真实总线替换 | 用 `bus-foundation` 替换 Swarm 底层 Mock Stub，下线本地 `event_bus.py` | 调研完成 | PLANNED |
| M3 | Mesh 动态反馈与 Omo 稳态落盘闭环 | Mesh 发生变更发布事件 -> Omo 订阅并校验 -> Ingress 锁原子写入 YAML 闭环 | M2 | PLANNED |
| M4 | 联合集成与自适应闭环测试校验 (E2E) | 编写 E2E 测试和联合集成测试，执行验证链 | M1, M2, M3 | PLANNED |

## Interface Contracts
### ECOS Workflow ↔ Agora MCP Gate
- **RPC 调用 endpoint**: `http://127.0.0.1:7422/v1/tools/call` (通过 httpx 调用 resolve_bos_uri)
- **参数结构**:
  - `uri`: `"bos://capability/swarm/run"`
  - `arguments`: `{"goal": str, "params": dict}`

### Swarm / Mesh ↔ Bus Foundation
- **发布接口**: `bus_foundation.publish(envelope: BusEnvelope) -> str`
- **事件信封结构**:
  - `plane`: `OmniPlane.EVENT`
  - `topic`: `"mesh:node:registered"`, `"mesh:node:updated"`, `"mesh:node:unregistered"`, 或是 Swarm 生命周期事件。
  - `source_uri`: `f"mesh://node/{node_id}"` 或 `f"swarm://..."`
  - `payload`: 包含节点属性的字典数据。

### Omo Ingress ↔ M1 YAML & system.yaml
- **锁定与写回接口**: `write_system_projection_fields` / `write_yaml_atomic`
- **约束规则**: `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`

## Code Layout
- ECOS Swarm 后端：`projects/ecos/src/ecos/workflow/backends/swarm.py`
- Swarm 底层事件及桩：`projects/aetherforge/packages/swarm/src/swarm_engine/`
  - `_events.py`
  - `lifecycle_events.py`
  - `_compat.py`
- Bus Foundation：`projects/bus-foundation/src/bus_foundation/`
- Mesh 网格：`projects/aetherforge/packages/mesh/src/compute_mesh/topology/registry.py`
- Omo Ingress 接口：`projects/omo/src/omo/omo_ingress.py`
- M1 稳态配置：`projects/ecos/src/ecos/ssot/mof/m1/`
