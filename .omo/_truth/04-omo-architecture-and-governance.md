# OMO 4.0 架构分析、审计与治理报告 (Architecture Audit & Governance)

> **核心摘要**：本文档基于最新实施的 OMO 双核联邦分形架构，对 `OMO 理论体系`、`projects/omo` (底层 OS 引擎)、`projects/omo-debt` (领域扩展工具) 以及 `.omo/` (实例数据湖) 进行了全面的架构审计与边界定义。其核心目标是实现“计算与状态分离”、“理论与工程同频”及“无限联邦扩展”。

---

## 1. 架构统一与宏观抽象 (Architecture Unity)

最新的 OMO 系统采用 **K1 (Kernel Engine) - K0 (Instance Data)** 的双核分形架构模式。

```mermaid
graph TD
    subgraph OMO_Theory["OMO 理论体系 (The Constitution)"]
        A[四平面理论: 事实/控制/知识/交付]
        B[联邦分形法则]
    end

    subgraph K1_Engines["计算面 (K1 Engine Plane) - 无状态"]
        C[projects/omo <br/>核心分发调度引擎]
        D[projects/omo-debt <br/>技术债务领域工具]
        E[Future: 其他组件...]
    end

    subgraph K0_Data["数据面 (K0 Data Plane) - 纯状态"]
        F[.omo/ (Workspace 级全局状态)]
        G[projects/kairon/.omo/ (子联邦级状态)]
    end

    OMO_Theory -.指导.-> K1_Engines
    OMO_Theory -.约束.-> K0_Data
    K1_Engines ==读/写==> K0_Data
```

**统一性原则**：
所有工具代码（如 Python 包）必须存在于计算面 (`projects/`)，所有流转状态和文档（YAML/MD）必须存在于数据面 (`.omo/`)。二者在物理目录上绝不允许交叉。

---

## 2. 职责边界与组件划分 (Boundaries & Responsibilities)

### 2.1 体系下的 OMO (理论与元法则)
*   **职责**：定义规则，作为多智能体 (Multi-Agent) 协作的**宪法**。包含“双核联邦架构”、“四平面法则”与“MCP 交互标准”。
*   **边界**：它不写一行代码，只提供 `.omo/standards/` 与 `.omo/_knowledge/` 中的文档支撑。
*   **状态**：极低频更新，变更需要发起 `Proposal`。

### 2.2 `projects/omo` (核心调度引擎)
*   **职责**：作为 OMO 操作系统的 Kernel (内核)。负责任务的分发 (Dispatch)、回收 (Reclaim)、多 Agent 并发锁控制 (Task Transaction) 以及全局规则评估。
*   **能力可靠性**：
    *   **极简依赖**：仅依赖 `pyyaml`，Python >= 3.13，保证启动速度毫秒级。
    *   **防脑裂机制**：内置基于 SQLite `EXCLUSIVE LOCK` 的文件锁 (`locks.db`)，确保多 Agent 抢占同一个 `.omo/tasks/` 时的事务原子性。
*   **边界**：绝不包含具体业务逻辑（如技术债如何计算）。它只管“流水线与心跳”。

### 2.3 `projects/omo-debt` (扩展领域引擎)
*   **职责**：这是一个专注于代码质量与技术债评估的**垂直领域工具**（Pattern 09 模型）。
*   **能力扩展性**：
    *   **独立技术栈**：它拥有自己的依赖生态（`click`, `rich`, `pydantic`, `gitpython`），支持复杂的报表渲染和计算。
    *   **即插即用**：作为一个独立的 CLI 工具 (`omo-debt`) 注册，未来可以被 `projects/omo` 编排，也可以被开发者直接独立调用。
*   **边界**：专注于计算与分析，它的分析结果最终会以 `.yaml` 或 `.md` 的形式回写进 `.omo/_control/debt-dashboard/`，交还给数据面。

### 2.4 `.omo/` (实例数据中心)
*   **职责**：作为 OMO 系统的存储底座，它是系统的 RAM 和 HDD。
*   **能力可靠性**：
    *   **四平面分离**：
        *   `_truth/` (唯一真相源：全局注册表)
        *   `_control/` (决策面：看板与状态机)
        *   `_knowledge/` (沉淀面：系统规划与架构图)
        *   `_delivery/` (交付面：历史验收记录与执行证据)
    *   **机器友好与人类友好兼顾**：通过 YAML (供程序解析) 和 Markdown (供人类和 LLM 阅读) 的组合保持数据的极致透明。
*   **扩展性**：支持**分形嵌套**。全局 `.omo/` 只管理跨域任务，而任何子项目 (如 Kairon) 都可以建立自己的 `.omo/` 管理局部内务。

---

## 3. 架构审计与缺陷修复总结 (Audit Findings)

在之前的治理行动中，我们发现了系统存在严重的“违建”问题，并已完成彻底的拔除：

| 异常现象 (已修复) | 违反的架构原则 | 治理动作 (Governance Action) |
| :--- | :--- | :--- |
| `.omo/debt/tooling/` 包含 `pyproject.toml` | 破坏了“计算与状态分离”原则，引擎代码混入了实例数据库中。 | 将整个文件夹平移至 `projects/omo-debt/`，作为独立应用管理。 |
| `.omo/tests/` 存放了 60+ 个 Python 测试脚本 | 破坏了“边界清晰”原则，OS 引擎的测试用例混入了交付面上。 | 提取到 `projects/omo/tests/`，从根本上隔离了代码验证和数据状态。 |
| OMO 内置脚本间的凌乱 `import` | 破坏了“能力可靠”原则，缺乏包管理支持导致运行脆弱。 | `scripts/omo` 升格为 `projects/omo`，引入 `uv` 标准包管理，使用纯粹的相对引用模块。 |

---

## 4. 未来演进与强扩展性规划 (Extensibility)

基于现有的高度解耦架构，未来系统的演进将变得极其顺畅：

1. **新 Agent 快速接入 (Plug & Play)**
   未来如果有新的 AI（如专门修复 Bug 的 Agent），它不需要去学习庞杂的 Python 代码。它只需要被引导去读取 `.omo/_truth/` 中的规则，并在 `.omo/tasks/` 中通过 `uv run omo worker dispatch` 认领任务即可。
2. **多语言子域自治 (Polyglot Sub-Federations)**
   由于 `.omo` 数据平面是语言无关的 YAML/MD。未来如果在 `projects/frontend/` 中引入了前端项目，即使开发语言是 TypeScript，它依然可以在自己目录下的 `.omo/` 中使用相同的四平面逻辑进行项目治理，甚至用 TS 写一个解析 `.omo` 的脚本，与全局系统的通信依然畅通。
3. **无限垂直引擎扩展 (Infinite Engines)**
   如果未来需要添加一个“文档生成引擎”或“安全扫描引擎”，我们只需在 `projects/` 下建立新的独立计算包（如 `projects/omo-security`），而绝不会污染主干的调度引擎 (`omo`)。
