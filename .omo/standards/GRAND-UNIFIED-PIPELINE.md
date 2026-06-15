# 🌌 大一统控制论全景架构 (The Grand Unified Cybernetic Pipeline)

> **Last Updated**: 2026-06-15
> **Status**: Official Core Doctrine (eCOS v5)
> **Purpose**: 阐明 C2G v4 (战略管线) 与先前积累的所有兵器库 (BMAD, OpenSpec, GSD, Superpowers, Model-Driven, OPC) 的全缝合逻辑。

---

## 🎯 核心错觉澄清

“引入 C2G v4 战略引擎，是不是意味着之前的 BMAD、OpenSpec 报废了？”
**绝对不是。**

之前的架构解决了 **“如何把事情做对 (Do things right)”** —— 也就是代码生成、架构推演和风控演练。
C2G v4 解决的是 **“如何做对的事情 (Do the right things)”** —— 它为盲目开动的战舰，安装了导航仪和方向盘。

所有的旧有组件，不仅没有失效，反而在 C2G 的框架下找到了最锋利的发力点。

---

## 🗺️ 全生命周期嵌套图谱 (The Unified Matrix)

从一个最抽象的愿景，到最后一行被 Push 到 main 分支的代码，这艘星舰的运转管线如下：

### 阶段一：意图降维与塑型 (The Head - Direction & Shaping)
> **目的**：把天马行空的想法，变成边界极度清晰的作战计划。

1. **Strategic Vision (北极星)**: 在 `VISION.md` 中定义核心向量（如 V1 人效, V2 自治）。
2. **Brainstorming (Superpowers)**: 唤醒 Agent 的 `Brainstorm` 技能，通过常规/进阶/疯狂三个维度发散。
3. **Shaping (C2G v4 Sandbox)**: 产出 `Pitch.md`。必须写明 `Appetite` (预算) 和 `No-Gos` (不做什么)。

### 阶段二：门禁与上下文锚定 (The Neck - Governance & Context)
> **目的**：拦截垃圾需求，把合法需求变成强契约。

4. **The Gatekeeper (L0 & OMO Bridge)**: 
   - 触发 `omo bridge`。
   - 底层拦截器 (`CR-STRATEGY-01`) 发威，没有 `Upstream` 锚点的 Pitch 被当场击杀。
   - 通过的 Pitch 进入 `.omo/goals/current.yaml` 成为正式 **Bet (下注)**。
5. **Context Flattening (BMAD)**: 
   - Bet 会派生出 `Task`。Task 中的 `context_uri` 会死死咬住原 `Pitch.md`。
   - Agent 拿到 Task，立刻触发 **BMAD (Beads Memory Anchor Document) 扁平化读取**。Agent 瞬间获得上帝视角，理解这头巨兽的全部初衷。

### 阶段三：架构与微观设计 (The Bones - Architecture)
> **目的**：在开写前，想清楚怎么写。

6. **Validation (Model-Driven)**: 
   - 所有的 Task 都是 M1 节点。底层的 `mof-schema-validate.py` (M2 校验器) 持续巡逻，确保 YAML 结构合法。
7. **Design (OpenSpec)**:
   - Agent 激活 **OpenSpec** 协议。根据 Pitch 中划定的边界，设计 API 接口、数据 Schema 和流转图。绝不越界。

### 阶段四：实兵落地与止损 (The Limbs - Execution & Yielding)
> **目的**：干活，并且在方向错了时立刻停下。

8. **Implementation (GSD - Get Shit Done)**: 
   - 按照 OpenSpec 的设计，开启 TDD 飞轮。写代码 -> 跑单测 -> 报错 -> 修复。
9. **Code Review (Superpowers)**: 
   - 代码写完，触发 `code-review` 技能视角，对 a11y、性能和隐患进行自我审查。
10. **Tactical Yield (战术退让)**: 
    - 如果 GSD 过程中遇到深坑，预计耗时将超过 Pitch 里的 `Appetite`，强制调用 `omo_yield_task` 举白旗投降。防范 LLM 陷入无限死循环的黑洞。

### 阶段五：免疫演练与结案聚变 (The Immune System - Defense & Write-back)
> **目的**：上线前过死神门禁，上线后经验反哺。

11. **Final Audit (OPC Self-Correction)**:
    - 进入 OPC P5-P7 演练模式。
    - L0 层死死守住 **5条红线**（如 `CR-CADENCE-01` 必须显式注入 INVOCATION_ID，`CR-MODE-ENV-01` 禁硬编码等）。任何一条不过，代码打回重做。
12. **SSOT Write-back (C2G 聚变)**:
    - 任务打上 `Done` 标签后，底层 `mof-extract` Git Hook 触发。
    - Agent 踩过的坑、最终实现的逻辑，被**自动原封不动地追加回** 最初的那份 `Pitch.md` 底部。文档完成了自我进化。

### 阶段六：熵减代谢 (The Excretory System - Entropy Reduction)
> **目的**：清理排泄物，防止系统臃肿。

13. **Garbage Collection (C2G v4 GC)**: 
    - 定期运行 `omo strategy gc`。Sandbox 中超过 28 天未下注的灵感垃圾，被全部打包流放至 `decayed/`。
14. **Vector Audit (战略雷达)**:
    - 运行 `omo strategy audit`。时刻确保整个大盘的火力，都集中在最初设定的 V1 和 V2 向量上。

---

## 💎 结语

通过这张拼图，**意图（Vision）**、**风控（OMO/OPC）**、**心智（BMAD/Superpowers）** 和 **手脚（GSD/OpenSpec）** 第一次达成了完美的融合。

这不是替代，而是**加冕**。

## 附录：全链路方法论流程抽象 (Process Abstractions)

为提升跨系统组件交互的规范性，将核心链路节点抽象为以下标准术语：

| 链路环节 | 动作转化 | 节点命名 (Acronym) | 工程学释义 |
| :--- | :--- | :--- | :--- |
| **01** | 愿景 ➡️ 提案 | **V2P** (Vision-to-Pitch) | **需求转化 (Requirement Translation)**：将抽象愿景解构为具备投入上限 (Appetite) 和范围禁区 (No-Gos) 的结构化提案。 |
| **02** | 提案 ➡️ 目标 | **C2G** (Concept-to-Goal) | **准入与定标 (Admission & Baselining)**：通过 OMO Bridge 拦截缺乏上游锚点 (Upstream) 的提案，将合规提案实例化为系统目标 (Bet)。 |
| **03** | 目标 ➡️ 语境 | **BMAD** (Beads-Memory-Anchor) | **语境扁平化 (Context Flattening)**：基于 `context_uri` 将层级化的背景知识降维为扁平上下文，保障执行单元的信息对齐。 |
| **04** | 语境 ➡️ 图纸 | **OSC** (OpenSpec-Constraint) | **模型约束设计 (Model-Constrained Design)**：在 M1/M2 数据架构强校验下，产出符合接口契约与状态流转规范的技术设计。 |
| **05** | 图纸 ➡️ 落地 | **GSD & TTY** (Get-Shit-Done & Tactical-Yield) | **迭代执行与超限熔断 (Iterative Execution & Threshold Yield)**：TDD 模式编码；当执行开销预估突破 Appetite 阈值时，强制触发 TTY 交出控制权，防范资源死锁。 |
| **06** | 落地 ➡️ 进化 | **OPC & SWR** (Op-Control & SSOT-Write-back) | **合规检查与状态回写 (Compliance Check & State Write-back)**：执行上线基线检查；流转结束时，将增量执行日志结构化追加至原始提案文档。 |
| **全局** | 系统 ➡️ 稳态 | **AGC** (Audit & Garbage-Collection) | **审计与回收 (Auditing & Reclaiming)**：通过基线审计评估战略向量偏离度，并依 28 天 TTL 阈值自动清理 Sandbox 闲置资源。 |
