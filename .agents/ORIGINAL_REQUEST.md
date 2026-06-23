# Original User Request

## Initial Request — 2026-06-23T02:25:45Z

对 eCOS 架构进行全局收敛与深度整合：将 AetherForge 与 ECOS 的跨层 subprocess 直连重构为 Agora I0 网格的 BOS 协议通信，以真实的 bus-foundation 替换 Swarm 底层 Mock Stub，并打通算力网格与 OMO 任务/稳态配置的自适应闭环控制。

Working directory: ~/teamwork_projects/ecos_architecture_convergence
Integrity mode: benchmark

## Requirements

### R1. Agora I0 MCP 跨层通信重构
将 ECOS 工作流对 AetherForge Swarm 的命令行直调，重构为通过 Agora MCP 服务网格 of BOS URI（如 `bos://capability/swarm/run`）形式进行标准 RPC 交互，彻底废弃易因虚拟环境依赖或路径偏移引发故障的 subprocess 直连。

### R2. Swarm 底层真实总线替换
使用系统中已有的 `bus-foundation` 模块，替换 `packages/swarm/src/swarm_engine/` 中对事件、消息及状态管理的兼容性 Stub，打通真实的蜂群多智能体协同控制与反馈总线。

### R3. Mesh 动态反馈与稳态配置闭环
实现自适应反馈闭环：
1. 底层 Mesh 探测到算力节点（例如 node 状态或 zone）发生变更时，不得通过 Raw I/O 直接修改稳态，而是向系统 `bus-foundation` 事件总线发布状态变更事件；
2. 由上层 Omo 治理引擎或 L4 Kernel 审计服务接收该事件，并按 SSOT 铁律执行安全校验与落盘，持久化修改 M1 元模型 YAML 稳态配置。

## Verification Resources & Methods

*   **R1 验证方法**：
    编写程序化监控脚本，运行 `ecos workflow run` 并跟踪系统进程与 Agora 审计日志。如果命令执行期间无任何针对 `aetherforge` 的子进程（subprocess）直调，且 Agora 记录了来自 ECOS 工作流的 `bos://` 路由调用，则视为通过。
*   **R2 验证方法**：
    在 `packages/swarm` 下建立测试集，使用单测运行 Swarm 任务，通过 AST 静态扫描或 Monkeypatch 拦截，验证其调用的消息 and 事件完全走 `bus-foundation`，且无任何指向 `_compat.py` 中遗留事件 Stubs 的调用。
*   **R3 验证方法**：
    编写自适应闭环集成测试脚本，模拟向算力网格中注册新节点或标记现有节点下线，验证在 10s 内相关的 M1 元模型 YAML 文件（如 `projects/ecos/src/ecos/ssot/mof/m1/compute_engine/` 目录下的对应配置）已被自动更新，且无未授权直写。

## Acceptance Criteria

### R1 ECOS 跨层调用
- [ ] 运行 `ecos workflow run` 时，Swarm 步骤成功通过 Agora I0 BOS 路由执行，审计日志中包含对应的 `bos://capability/swarm/run` 记录。
- [ ] 系统运行期无任何 `aetherforge swarm` 命令的 subprocess 子进程生成。

### R2 Swarm 真实总线
- [ ] 运行蜂群任务时，所有的智能体间广播和感知调用均由 `bus-foundation` 统一承载。
- [ ] AST 扫描确认 `swarm_engine/` 所有核心执行文件没有针对 `_compat.py` 里事件与消息 Stub（如 `_emit_hatcher_event` 等）的活跃引用。

### R3 自适应闭环控制
- [ ] 在节点状态改变事件发出后，M1 稳态 YAML 在 10 秒内自动触发持久化更新对齐。
- [ ] 所有的 YAML 修改操作均由 `omo` 治理服务安全写回，没有 raw file write 的治理漂移。
