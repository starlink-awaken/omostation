---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# C2G v2 (Cybernetic-to-Governance) 体系架构演进契约

## 1. 架构目标与背景
基于 eCOS v5 体系，原有的 C2G (Creative-to-Governance) 暴露出了降维灾难、桥接层脆弱、缺乏柔性回滚、重型审批开销等瀑布流缺陷。
本契约 (OpenSpec) 旨在定义 C2G v2 的双向柔性演进方案，将单向工厂流水线升级为带有负反馈回路的控制论系统。

## 2. 核心架构升级说明

### 2.1 引入 BOS URI 双向寻址锚点 (Context Symlink)
*   **设计原则**：YAML (M1 Node) 仅承载状态与核心约束，详细上下文驻留知识面。
*   **API/数据流**：在所有 `omo_task.yaml` Schema 中，隐式支持或显式新增 `context_uri` 字段，格式为 `bos://memory/...`。
*   **X1-X4 声明**：不打破 X4 (SSOT) 唯一事实来源，知识面作为不可变事实源，任务流作为业务状态。

### 2.2 架构双轨制与“免签快车道” (Fast-Track Bypass)
*   **设计原则**：区分微观迭代与宏观架构，降低认知能耗。
*   **机制**：`workspace iterate` 加入复杂度路由。Mode B 极低复杂度任务直接生成 `lightweight-task.yaml` 越过 MetaOS 沙箱期。

### 2.3 状态机柔性回滚 (Yield to Ideation)
*   **设计原则**：打通 Phase IV/III 到 Phase I 的反向回传链路。
*   **API/数据流**：在 OMO 任务状态机中，新增合法状态 `yield_to_ideation` (挂起并退回发散)。触发时，由 Agent 调用 `omo_yield_task` 发送失败堆栈，自动将其打包回传至沙箱 Context 供二次脑暴。

### 2.4 Schema 逆向推导引擎
*   **设计原则**：消灭大模型文本提取 YAML 的幻觉。
*   **机制**：桥接器 `omo_bridge_openspec` 在输出端必须先读取确切的 Pydantic 模型 (m2/omo_task.yaml)，发起强结构化请求，并实施 `pydantic.model_validate()` 拦截脏数据。

## 3. 落地排期规划
*   第一步：更新系统核心设计文档 `C2G-Pipeline-Design.md` 融入 v2 理念。
*   第二步：在 M2 Schema 中评估/测试注入 `context_uri` 及 `yield_to_ideation` 状态。
*   第三步：打通 MetaOS 和 OMO 的异常重送工作流。
