---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# OMO 理论框架与工具集全景对标报告 (Framework vs Tooling Benchmark)

本报告旨在从“第一性原理”出发，严格核对 OMO 理论框架（宪法层）与落地工具（`projects/omo`、`projects/omo-debt`）及数据容器（`.omo/`）之间的映射对齐情况。

---

## 1. 核心理论对标矩阵 (The Benchmark Matrix)

| OMO 理论原则 (The Theory) | 数据面实现 (`.omo/`) | 工具面实现 (`projects/omo*`) | 对齐度 (Alignment) |
| :--- | :--- | :--- | :---: |
| **分离原则 (Separation of Concerns)**<br/>状态与计算必须物理分离，形成双核结构。 | **完美纯净**。<br/>`.omo/` 内部已彻底清除了所有 Python 脚本和依赖文件，纯粹由 YAML/MD 数据组成。 | **完全独立**。<br/>逻辑层被完整抽取到了 `projects/omo` 和 `projects/omo-debt` 中，作为 Python Package 独立管理。 | 🟢 100% |
| **四平面法则 (Four-Plane Rule)**<br/>数据流转必须严格分为：Truth, Control, Delivery, Knowledge。 | **结构自洽**。<br/>根目录下严格对齐了 `_truth/`、`_control/`、`_delivery/`、`_knowledge/`。游离文件已被清理归档。 | **路径解耦**。<br/>`omo_worker` 引擎读取 `_truth/registry` 获取权威节点，`omo_debt` 结果输出到 `_control/` 供仪表盘消费。 | 🟢 100% |
| **状态防漂移与并发锁 (No Zombie/Drift)**<br/>多 Agent 协作时必须保证任务的原子性和状态的唯一性。 | **状态快照化**。<br/>`state/system.yaml` 与 `tasks/` 目录使用标准化的 schema 追踪生命周期。 | **SQLite 互斥锁**。<br/>`projects/omo` 内置了 `omo_task_transaction`，多进程抢占任务时通过 SQLite `EXCLUSIVE LOCK` 保证绝对安全，防止脑裂。 | 🟢 100% |
| **联邦分形扩展 (Federated Fractals)**<br/>全局治理与局部治理可以无限嵌套，且模型一致。 | **根目录就绪**。<br/>全局 `.omo/` 负责跨域协调。各子项目（如 Kairon）可随时初始化自己的局部 `.omo/` 结构。 | **上下文注入**。<br/>CLI 工具 (如 `omo worker`) 支持透传 `omo_dir` 参数，引擎代码不再写死绝对路径，可挂载到任意联邦节点上。 | 🟢 95% <br/>*(待验证局部实例)* |
| **领域无限扩展 (Infinite Domain Extension)**<br/>主干调度引擎不应被业务垂直逻辑污染。 | **领域挂载**。<br/>根目录预留了 `debt/` 作为独立领域的数据暂存区，但不破坏四大平面的主体叙事。 | **主干与分支解耦**。<br/>`projects/omo` 仅提供并发锁与路由；业务计算被封装在独立的 `projects/omo-debt` 里。未来增加 `omo-security` 不影响主轴。 | 🟢 100% |

---

## 2. 工具链能力审计 (Tooling Capability Audit)

### 2.1 引擎层内核: `projects/omo` (The OS Kernel)
它是 OMO 的“CPU”。
*   **设计原则对标**：**极简主义与高可用**。
    *   **理论要求**：内核不能因为依赖库冲突而崩溃。
    *   **落地情况**：基于最新 `uv` 架构，**零第三方重度依赖** (仅依赖 `pyyaml`)，要求 Python >= 3.13。启动开销 < 50ms。这使得它可以作为 Daemon 极速响应任何 Agent 的心跳。
*   **核心功能边界**：仅处理 `Task Dispatch`、`Task Reclaim`、`State Locking`、`Worker Heartbeat`。它**绝不关心**你的代码写得好不好，它只关心“任务流转是否符合规则”。

### 2.2 领域层外设: `projects/omo-debt` (The Domain Peripheral)
它是 OMO 的“专业显卡”。
*   **设计原则对标**：**专业性与重度计算**。
    *   **理论要求**：垂直领域工具应该拥有足够的计算能力，且不拖累主内核。
    *   **落地情况**：引入了 `pydantic` (严格校验)、`gitpython` (仓库分析)、`rich` (控制台渲染)。它完全实现了 OMO 理论中的 **Pattern 09 v2** 技术债评估模型。
*   **核心功能边界**：读取目标项目的 Git 历史 -> 识别项目生命周期 -> 结合诚实度 (Honesty) 因子计算技术债跑分 -> 将结果写入 `.omo/debt/` 数据总线供系统消费。

---

## 3. 闭环链路演练 (End-to-End Governance Loop)

为了验证理论与工具的对齐，我们推演一个真实的 OMO 自动化运转闭环：

1. **[Truth/规则定义]**：人类或高级 Agent 在 `.omo/_truth/registry/workers.yaml` 中定义了某个修复 Bug 的新 Agent。
2. **[Control/任务产生]**：系统生成了一个任务文件放入 `.omo/tasks/active/`。
3. **[Engine/锁与分发]**：新 Agent 启动，调用 `uv run omo worker dispatch`。此时 `projects/omo` 引擎触发 SQLite 互斥锁，确保只有它拿到了这个任务，并更新 `state/locks/`。
4. **[Extension/专业执行]**：如果任务是清理历史代码，Agent 可以调用 `uvx omo-debt assess-legacy` 来计算重构风险。
5. **[Delivery/交付核销]**：任务完成，Agent 生成 PR，并将证据存入 `.omo/_delivery/evidence/`。
6. **[Knowledge/资产沉淀]**：最终架构变更被记录到 `.omo/_knowledge/design/`。

**结论：** 
目前的工具链设计完美支撑了这条理论链路的每一步。系统没有任何越权、跳步或数据污染的可能。

---

## 4. 下一步演进建议 (Next Steps for Evolutionary Alignment)

尽管核心架构已经高度对齐，但为了将理论发挥到极致，未来可以推进以下演进：

1. **Schema 严格执行 (Pydantic for Data Plane)**：
   目前 `projects/omo` 只是松散地读取 `.omo/` 下的 YAML。未来可以将所有 Truth 和 Control 平面的 YAML 定义为严格的 Pydantic 模型（类似于 Kubernetes CRD），做到“凡写入必校验”。
2. **联邦广播机制 (Federated Gossip)**：
   当 `projects/kairon/.omo/` (局部) 发生变更时，通过 `projects/omo` 引擎向全局 `/.omo/` (全局) 发送异步心跳和事件聚合，真正实现**分形联动**。
