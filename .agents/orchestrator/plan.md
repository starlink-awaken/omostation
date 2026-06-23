# Project Plan: eCOS Architecture Convergence (eCOS 架构收敛与整合)

本计划旨在重构 AetherForge 与 ECOS 的跨层 subprocess 直连为 Agora I0 网格的 BOS 协议通信，以真实的 `bus-foundation` 替换 Swarm 底层 Mock Stub，并打通算力网格与 OMO 任务/稳态配置的自适应闭环控制。

## Milestones (里程碑分解)

| 里程碑 | 目标 | 依赖项 | 验证标准 | 状态 |
|---|---|---|---|---|
| **M1: Agora I0 MCP 跨层通信重构** | 废弃 subprocess 直调，重构为 Agora BOS RPC 路由调用 `bos://capability/swarm/run` | 调研报告已输出 | 运行 `ecos workflow run` 无 subprocess 直调且 Agora 日志有 `bos://capability/swarm/run` 记录 | PLANNED |
| **M2: Swarm 底层真实总线替换** | 以系统已有的 `bus-foundation` 替换 `packages/swarm/src/swarm_engine/` 兼容 Stub，清理本地 `event_bus.py` | 调研报告已输出 | 蜂群单测通过，AST 扫描无遗留桩调用，`bus-foundation` 承载广播与感知 | PLANNED |
| **M3: Mesh 动态反馈与 Omo 稳态落盘闭环** | Mesh 节点变更发布 bus-foundation 事件，Omo 后台接收并按安全审计机制原子写回 M1 元模型 YAML 及 system.yaml | M2, 现有的 Omo 接口 | 触发节点变动后 10 秒内静态 YAML 及 system.yaml 自动更新，且包含审计轨迹，无未授权直写 | PLANNED |
| **M4: 联合集成与自适应闭环测试校验 (E2E)** | 编写整体集成测试脚本，覆盖 R1、R2、R3 链路 | M1, M2, M3 | 联合集成测试通过，在 benchmark 模式下表现稳定，全流程无破坏一致性操作 | PLANNED |

---

## 详细执行步骤与验证规划

### M1. Agora I0 MCP 跨层通信重构

#### 步骤 1.1: 在 Agora 中注册与实现 `bos://capability/swarm/run`
1. 修改 `projects/agora/etc/bos-services.yaml`，注册 `bos://capability/swarm/run` 资源定位与内部/外部 RPC 服务绑定。
2. 在 Agora 网格服务中（如 `agora/mcp/swarm.py`，或合适的服务位置），实现 RPC 接口的接收逻辑 `run_swarm_task(goal, params)`，该接口通过 AetherForge Swarm API 执行具体的蜂群任务，并返回标准 JSON。
3. **独立验证**：使用命令行工具或测试脚本单独调用 `resolve_bos_uri` 来触发 `bos://capability/swarm/run`，验证其正确分发并返回。

#### 步骤 1.2: 重构 ECOS 工作流后端对 Swarm 的调用
1. 修改 `projects/ecos/src/ecos/workflow/backends/swarm.py`。
2. 在 `_execute_step_swarm` 函数中，使用 `httpx` 向 Agora Gateway 发送 RPC 调用请求：
   * 目标端点：`http://127.0.0.1:7422/v1/tools/call` 或 `7431`（依据配置）
   * 工具：`resolve_bos_uri`
   * 参数：`{"uri": "bos://capability/swarm/run", "arguments": {"goal": goal, "params": params}}`
3. 保留原有命令行 subprocess 调用逻辑作为 fallback 降级。
4. **独立验证**：运行 `ecos workflow run`，拦截进程并捕获 `aetherforge swarm` 命令，确保无任何 subprocess 运行，且 Agora 网格上有对应 RPC 日志。

---

### M2. Swarm 底层真实总线替换

#### 步骤 2.1: 替换事件与生命周期发布逻辑
1. 修改 `projects/aetherforge/packages/swarm/src/swarm_engine/_events.py`：
   * 移除对本地 `.event_bus` 的引用。
   * 引入 `bus_foundation`，在 `_emit_hatcher_event` 中构造并发布 `BusEnvelope` 信封。
2. 修改 `projects/aetherforge/packages/swarm/src/swarm_engine/lifecycle_events.py`中的 `SwarmEventEmitter.emit`，使其统一通过 `bus-foundation` 分发。

#### 步骤 2.2: 清理并移除事件 Stub
1. 确认无其他文件对 `packages/swarm/src/swarm_engine/event_bus.py` 的依赖。
2. 彻底下线并删除 `event_bus.py`。
3. 清理 `_compat.py` 中不再使用的事件桩。
4. **独立验证**：运行 `packages/swarm` 下的单元测试确保无报错，使用静态 AST 分析（或者 grep）确保 `_compat.py` 的事件桩已无活跃引用。

---

### M3. Mesh 动态反馈与 Omo 稳态落盘闭环

#### 步骤 3.1: Mesh 网格事件广播
1. 在 `projects/aetherforge/packages/mesh/src/compute_mesh/topology/registry.py` 的 `NodeRegistry._notify` 中引入 `bus-foundation`。
2. 当发生 `registered` / `updated` / `unregistered` 操作时，向 `bus-foundation` 广播发布 `mesh:node:registered` / `mesh:node:updated` / `mesh:node:unregistered` 事件。

#### 步骤 3.2: 建立 Omo 后台订阅与审计写回机制
1. 在 Omo 后台接收器（或者 L4 Kernel 守护进程）中引入 `bus_foundation.subscribe("mesh:node:*")`。
2. 编写回调逻辑，解析节点变更事件，并按照 `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` 约束执行合规性检查。
3. 校验通过后，调用 `write_system_projection_fields` 原子写入 `.omo/state/system.yaml` 状态面，并调用 `write_yaml_atomic` 将更新写入到 M1 元配置 YAML（例如 `projects/ecos/src/ecos/ssot/mof/m1/compute_engine/` 的对应节点配置中）。
4. 保证在写回操作中触发 `record_audit` 和 `_record_trail` 记录审计轨迹。
5. **独立验证**：运行节点变动，观察 `.omo/state/system.yaml` 和对应的 M1 元配置 YAML 在 10 秒内同步更新，且 `/Users/xiamingxing/Workspace/.omo/` 没有 raw file direct-write，且生成了规范的审计文件。

---

### M4. 联合集成与自适应闭环测试校验 (E2E)

1. 编写包含全链路的端到端集成测试脚本。
2. 在该测试脚本中：
   * 启动 Agora 网格及事件服务。
   * 注册 Mesh 节点变更，验证在 10s 内 M1 配置文件及 system.yaml 发生同步且包含审计记录。
   * 执行 `ecos workflow run`，校验无 aetherforge 子进程启动，且网格调用成功记录。
3. 运行根 Makefile 下的 `governance-verify` 验证链以确保不产生任何治理漂移。
