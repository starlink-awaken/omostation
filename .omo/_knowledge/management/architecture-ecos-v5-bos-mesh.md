# eCOS v5 终态架构大一统映射 (Grand Unification)

> **状态**: Active (Phase 33 确立)
> **核心原则**: 一切皆 URI (Everything is an URI)；动态注册与反向代理 (Dynamic Registry & Reverse Proxy)。

## 1. 架构总览 (5+3+1 升级版)

eCOS v5 在原有的 5+3+1 分层基础上，通过引入 **BOS URI** 和 **Agora Mesh**，实现了各个物理包和组件的逻辑大一统。

*   **L4 (自我层)**: Cockpit Terminal，向 Agora 发起 `bos://` 请求。
*   **I0 (织层)**: Agora，作为纯粹的反向代理和网关，根据动态路由表将请求分发给背后的 L2/L1/L0 提供者。
*   **L2-L0 (提供者)**: 各引擎以 Daemon 模式启动，向 Agora 宣告自己的 `bos://` 命名空间和 MCP 工具。

## 2. 5 大神圣领域挂载图谱

### 🏛️ 域 1：记忆与事实源 (The Memory Domain) `bos://memory`
负责守护绝对的物理与知识真相。
*   **`bos://memory/kos/*`** ➡️ **[Provider: `kairon/kos`]** 跨域索引与全局搜索。
*   **`bos://memory/kronos/*`** ➡️ **[Provider: `kairon/kronos`]** 摄取管线。
*   **`bos://memory/gbrain/*`** ➡️ **[Provider: `projects/gbrain`]** 结构化数据的时序数据库访问点。
*   **`bos://memory/ssot/*`** ➡️ **[Provider: `kairon/sot-bridge`]** 全域 Single Source of Truth。

### ⚖️ 域 2：治理与律法 (The Governance Domain) `bos://omo`
负责决定“能做什么”、“对不对”以及运行流转机制。
*   **`bos://omo/metaos/*`** ➡️ **[Provider: `projects/metaos`]** L2 编排引擎、决策门控与免疫机制。
*   **`bos://omo/eidos/*`** ➡️ **[Provider: `kairon/eidos`]** Schema 定义与校验约束。
*   **`bos://omo/protocols/*`** ➡️ **[Provider: `kairon/protocols-layer`]** Sophia 范式编译与 Symphony 状态机规则。

### 🧠 域 3：认知与推演 (The Analysis Domain) `bos://analysis`
大模型进行逻辑计算和降维打击的暗室。
*   **`bos://analysis/code/*`** ➡️ **[Provider: `kairon/codeanalyze`]** AST 级别的代码库理解。
*   **`bos://analysis/derive/*`** ➡️ **[Provider: `kairon/ontoderive`]** 事实推导引擎。
*   **`bos://analysis/research/*`** ➡️ **[Provider: `kairon/minerva`]** 深度研报生成和信息抽取引擎。

### 🎭 域 4：人格与心智 (The Persona Domain) `bos://persona`
控制大模型表现层，实现 BDSK 虚拟董事会切换。
*   **`bos://persona/sharedbrain/*`** ➡️ **[Provider: `kairon/sharedbrain-bridge`]** 基因指令与反脆弱人格封装。

### 🚀 域 5：能力与生态 (The Capability Domain) `bos://forge`
操作系统的“应用商店”和执行环境。
*   **`bos://forge/registry/*`** ➡️ **[Provider: `kairon/forge`]** 工具、插件、技能与工作流的主注册表。
*   **`bos://forge/runtime/sandbox`** ➡️ **[Provider: `projects/runtime`]** KEI 安全执行沙箱。
*   **`bos://forge/observability`** ➡️ **[Provider: `kairon/kairon-observability`]** 系统的遥测与监控打点。

## 3. 全层级深层联动机制

### 3.1 🛡️ `metaos` 的免疫与熔断 (The Immune System)
- **联动 I0**: `metaos` 旁路监听 Agora。若发现恶意或死锁请求，瞬间切断该 Session 的 MCP 路由。
- **联动 X1**: 高危指令前置拦截，交由 Runtime KEI 沙箱模拟执行，通过后放行。
- **联动 L0**: 重大决策直接作为 Message 写入 `ecos` SSB 的 Immutable Log（治理区块链）。

### 3.2 🧬 `eidos` 的中间件清洗 (The Filter)
- **联动 I0**: `eidos` 作为 Agora 反向代理的 Middleware。所有流入 L2 引擎的 JSON 载荷必须通过动态 Schema 校验，实现“御敌于国门之外”。
- **联动 X3**: 评估抽取该知识的 Schema 成本，结合 `llm-gateway` 的 Token 消耗，ROI 过低则拒绝执行。

### 3.3 ⚙️ `protocols` 的涌现计算与自愈 (The Laws of Physics)
- **联动 L0**: `sophia` 与 `symphony` 的规则被编译为智能合约，广播至 `ecos` P2P 层，实现多设备的涌现计算。
- **联动 L1**: Symphony 状态机触发时，联动 Runtime Scheduler，凭空产生幽灵进程 (Ephemeral Agents) 执行任务，事毕销毁。
- **联动 X2**: 真实状态若偏离 Symphony 期望状态，触发 Autoheal 进行抗熵修复。

## 4. Forge 集市热加载生命周期
1. **发现**: 大模型缺工具时，查询 `bos://forge/registry/tools`。
2. **下载**: 缺失工具时，通过 `market_load_tool` 从云端/GitHub 获取。
3. **挂载**: 下载至内存或 `.omo/capabilities/`。
4. **宣告**: 插件作为独立 Daemon 启动，通过 HTTP 向 Agora 宣告自己的 `bos://` 前缀及能力。
5. **执行**: 大模型立刻无缝调用新能力，全过程零重启。
