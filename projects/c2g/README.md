# C2G Engine (Concept-to-Goal)

> 🧭 **The Strategic Compass for eCOS v6**

C2G 引擎是 eCOS 的“战略管控大脑”。它负责接收未经雕琢的原始意图（Pitch），验证其合规性与边界（Appetite），并将其降维、转换、下注为系统可追踪、可执行的战略目标（Bet & Task）。

## 核心职责 (Responsibilities)

1. **V2P (Vision-to-Pitch)**: 协助将模糊愿景转化为包含边界的结构化提案（沙箱阶段）。
2. **C2G (Concept-to-Goal)**: 在 `omo` 治理门控的强力监督下，将合规的 Pitch 实例化为 L4 目标。
3. **AGC (Audit & Garbage-Collection)**:
   - **战略雷达 (Radar)**: 审计全盘活跃目标的愿景偏离度。
   - **熵减清理 (GC)**: 回收 Sandbox 中长期（> 28天）未下注的僵尸提案。

## 架构边界 (Architecture Context)

*   **物理层级**: L2 引擎层 (Engine Layer)
*   **交互入口**: L3 入口层经由 `workspace compass` 宏指令暴露给终端用户。
*   **数据载体**: 读取 `runtime/sandbox/pitches/*.md`，输出 L4 `current.yaml` (目标) 与 `.omo/tasks/planned/*.yaml` (任务)。

## 当前耦合限制 (Coupling Limitations)

*⚠️ 注意：本项目目前深度嵌入于 starlink-awaken/omostation Monorepo，尚未实现真正的物理隔离与外部独立使用。*

*   **治理耦合**: 硬依赖于 `projects/omo` 提供的 `omo.omo_goal` 与 `omo.omo_task_schema` 进行状态写入与模型校验。
*   **基建耦合**: 强依赖于工作区根目录下的 `.omo/` 与 `runtime/` 文件夹结构。
*   **协议耦合**: 暂未接入 `agora` 的 BOS URI，而是直接通过 Python API 跨域调用 OMO。
