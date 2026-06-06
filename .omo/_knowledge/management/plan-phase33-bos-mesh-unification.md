# Phase 33: BOS URI & Agora Mesh Unification

> **目标**: 实现 eCOS v5 终态架构大一统，通过 BOS URI 与 Agora Mesh 完成“知、魂、行”的物理层与协议层统一。
> **前置条件**: Phase 30-32 完成（L0-L4 物理拆包、观测性基建、治理下沉）。

## 核心战役 (Campaigns)

### 战役 1：Agora 织层重塑与动态注册 (I0)
- **目标**: 彻底废除 Agora 内的硬编码 Import，实现真正的 Service Mesh 动态反向代理。
- **Action Items**:
  - [ ] **1.1** 在 Agora 中实现 `Registry Server`，接受子系统通过 HTTP/SSE/stdio 的动态注册心跳。
  - [ ] **1.2** 为各个核心包 (`omo`, `forge`, `kos`, `metaos` 等) 开发/完善独立的 Daemon 启动脚本。
  - [ ] **1.3** 各 Daemon 启动时，主动向 Agora 宣告接管的 `bos://` 命名空间前缀及携带的 MCP Tools。
  - [ ] **1.4** Agora 内部实现动态内存路由表 (DHT or Map)，透明化反向代理所有请求。

### 战役 2：全域 BOS URI 挂载 (The 5 Domains)
- **目标**: 将 25+ 物理子包的能力，全面封装并映射为 5 大神圣领域的 BOS 资源。
- **Action Items**:
  - [ ] **2.1 (Domain 1: Memory)** `kairon/kos` 注册 `bos://memory/kos/search` 等核心端点；`kairon/kronos` 注册 `bos://memory/kronos/ingest`。
  - [ ] **2.2 (Domain 2: Governance)** `metaos` 注册免疫门控节点；`eidos` 注册 `bos://omo/eidos/schemas` 并作为中间件阻挡畸形数据；`protocols-layer` 注册智能合约触发器。
  - [ ] **2.3 (Domain 3: Analysis)** `ontoderive`, `minerva`, `codeanalyze` 提供推演与研报端点。
  - [ ] **2.4 (Domain 4: Persona)** 迁移/注册 `sharedbrain-bridge` 与 `core-models`。
  - [ ] **2.5 (Domain 5: Capability)** 激活 `kairon/forge` 作为应用商店，挂载 `bos://forge/registry/tools` 等资源。

### 战役 3：Forge 集市与热加载机制 (Dynamic Capabilities)
- **目标**: 激活 eCOS 的自动适应力，实现能力的“云端发现 -> 用时加载 -> 本地固化”闭环。
- **Action Items**:
  - [ ] **3.1** 复活/重构 `plugins/market`，接入 `bos://forge`。
  - [ ] **3.2** 实现 `market_load_tool` MCP 工具：大模型一键拉取 Github 插件库。
  - [ ] **3.3** 工具在临时内存或 `.omo/capabilities/` 磁盘挂载，并自动向 Agora 注册，实现零重启扩容。

### 战役 4：X 侧链与 L0 锚定 (Immutable Governance)
- **目标**: 实现决策上链与底层沙箱熔断。
- **Action Items**:
  - [ ] **4.1** `metaos` 的免疫判定逻辑联动 `runtime` (X1 KEI Sandbox) 实现高危代码运行前置审查。
  - [ ] **4.2** `metaos` 和 `protocols-layer` 产生的重大流转与决策，强制调用 `ecos` SSB 协议写入 L0 append-only log。
  - [ ] **4.3** `eidos` 校验失败记录与 `llm-gateway` 成本消耗 (X3) 触发 `symphony` 的惩罚或降级状态跳跃。

## 成功衡量标准 (Definition of Done)
1. **零硬编码**: Agora 代码库中完全没有任何特定业务包的 `import` 语句。
2. **热插拔**: 停止 `omo` 进程后，大模型请求 `bos://omo/debt` 会收到超时或 404；重新启动后立即恢复，且期间不影响其他域的正常工作。
3. **即插即用插件**: 测试通过大模型发送一个 GitHub 仓库链接，系统能自动将该仓库作为新插件热挂载，大模型立刻就能使用新工具。
