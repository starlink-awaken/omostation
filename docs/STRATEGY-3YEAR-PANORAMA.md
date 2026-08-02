---
title: eCOS v6 愿景驱动的长期架构与战略执行方案
status: active
type: strategy
owner: 夏明星
created: 2026-07-15
updated: 2026-08-01
horizon: 2026H2-2029
version: v1.0
lifecycle: contract
last-reviewed: 2026-08-02
review-state: evidence-refreshed
related:
  - docs/VISION-ROADMAP.md
  - docs/PROJECT-COMPLETE-GUIDE.md
  - docs/ARCHITECTURE-EVOLUTION.md
  - docs/proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md
  - .omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md
  - .omo/_knowledge/decisions/0247-strategic-pivot-collab-first-physical-deferred.md
  - .omo/_knowledge/decisions/0297-external-connection-fabric-and-product-truth.md
  - .omo/_knowledge/decisions/0298-external-connection-fabric-runtime-boundary.md
  - .omo/_truth/registry/external-connection-fabric.yaml
  - .omo/standards/external-connection-fabric.md
note: >
  本文是战略叙事与执行框架，不拥有当前 Phase、健康分、服务数、项目数、端口、
  测试数或任务数。所有运行时事实必须从对应 SSOT 动态读取，不得从本文反向抄录。
---

# eCOS v6 愿景驱动的长期架构与战略执行方案

## 1. 执行结论

eCOS 已经完成从零散工具集合到受治理 AI 操作系统骨架的跨越。协议、运行时、知识、
治理、算力、入口和证据链均已有真实实现，下一阶段的主要矛盾不再是“缺少能力”，而是：

1. 能力数量增长快于用户主路径收敛。
2. 战略、运行状态、项目注册表和 Git 仓库身份存在不同步风险。
3. 多个引擎在编排、状态、路由和记忆方面仍有职责交叉。
4. 治理成熟度高于真实场景使用频率，容易继续优化图纸而非产品结果。
5. 部分“智能化”能力已经有入口和契约，但尚未形成基于上下文、评测和反馈的真实适应。

因此，未来三年的战略不再按新增 Phase 或新增子项目推进，而按三条可重复的黄金旅程推进：

- 工程交付闭环。
- 知识到行动闭环。
- 受控多 Agent 协作闭环。

一句话战略：

> 把 eCOS 收敛成个人智能执行操作系统：用户只表达一次意图，系统完成理解、规划、
> 隔离执行、验证、交付、记忆和改进，全过程可暂停、可解释、可恢复、可回滚。

## 2. 事实口径

本文只定义方向、边界和阶段门槛。动态事实的权威来源如下：

| 事实 | 权威来源 |
|---|---|
| 当前 Phase、任务、健康与运行状态 | [`.omo/state/system.yaml`](../.omo/state/system.yaml) |
| 当前目标 | [`.omo/goals/current.yaml`](../.omo/goals/current.yaml) |
| 项目元数据 | [`docs/project-registry.yaml`](project-registry.yaml) |
| BOS 能力与路由 | [`projects/agora/etc/bos-services.yaml`](../projects/agora/etc/bos-services.yaml) |
| 稳定架构契约 | [`ARCHITECTURE.md`](../ARCHITECTURE.md) |
| 真实交付门禁 | [`docs/G-DEL-PHASE2-BOARD.md`](G-DEL-PHASE2-BOARD.md) |
| 任务与执行台账 | [`.omo/tasks/registry/INDEX.md`](../.omo/tasks/registry/INDEX.md) |
| 决策记录 | [`.omo/_knowledge/decisions/INDEX.md`](../.omo/_knowledge/decisions/INDEX.md) |

任何战略评审必须同时检查声明、可解析入口、真实执行和用户结果，不得用文件存在、
schema 通过或模拟 harness 代替真实完成。

## 3. 对愿景与使用者的理解

eCOS 的目标使用者首先是系统所有者本人。核心需求不是拥有更多工具，而是获得一个：

- 不丢工作、不覆盖成果、可以安全并行的执行系统。
- 能积累个人知识、决策依据和长期偏好的外置大脑。
- 能把复杂意图拆成受治理执行，并持续交付结果的数字副官。
- 本地优先、数据可控、云边可切换的私有智能底座。
- 可以演进，但不会绕过人类授权直接改变生产状态的受控系统。

系统所有者具有强烈的长期主义和体系化倾向。这是架构完整性的来源，也带来一个需要机制化
约束的风险：能力可能在真实场景出现前被提前建设到完整形态。后续采用“场景激活门”控制投资：

1. 有明确使用者和可重复意图。
2. 在连续四周内存在真实需求或明确机会窗口。
3. 有可量化结果，而非仅有技术完成定义。
4. 数据权限、操作责任和人工接管方式明确。
5. 现有平台无法通过配置或领域包满足。

未通过激活门的能力保留契约、测试和证据，但冻结新增投入。KEMS 与 Family Hub 当前按此规则管理。

## 4. 当前阶段判断

项目处在“平台能力齐备、产品兑现开始、状态真相需要归一”的转折点。

已经具备：

- Cockpit 人类入口和 Agora Agent 路由。
- OMO 任务、治理、审计、证据和 Agent Workflow。
- Runtime 执行、沙箱、注册、同步和故障处理基础。
- AetherForge 网关、Mesh、Swarm 和本地算力接入。
- Kairon/KOS 与 gbrain 的知识处理、检索和持久化能力。
- ECOS、MOF、X1-X4 和 GaC 的协议与治理资产。

尚未真正完成：

- 一条被持续使用、可测量业务收益的端到端产品主路径。
- 项目注册表、current goals、运行投影与仓库远端身份的统一时间线。
- 编排、策略、执行、状态和知识真相之间的最终职责收敛。
- 基于真实上下文、评测集、置信度、成本和反馈的自适应智能。
- 真实物理多机门禁；该能力按既有决策继续 deferred，不占当前主轴。

## 5. 北极星与战略原则

### 5.1 北极星指标

北极星指标是“每周成功完成并被实际消费的闭环旅程数”。一次闭环必须同时满足：

- 有明确用户意图。
- 通过统一入口进入。
- 经过受治理的计划和执行。
- 产生用户可消费结果。
- 留下可验证证据和可复用记忆。
- 失败时可恢复、可解释或可回滚。

### 5.2 战略原则

1. 场景拉动架构，禁止为未知需求新增顶层项目。
2. 一个受众一个入口：人类走 Cockpit，Agent 走 Agora，治理写入走 OMO broker。
3. 一个事实一个所有者，派生索引必须可从权威源重建。
4. 产品与用户旅程投入不低于 70%，治理与元模型投入不高于 30%。
5. 单机主路径先稳定，再扩大到多 Agent 和多设备。
6. 任何“智能化”声明必须有上下文、评测、成本、置信度和回滚证据。
7. 自进化只能生成受治理提案，不能直接修改生产真相。
8. 外部知识、数据、方法、工具、模型和渠道必须通过统一连接织层接入，并绑定真实场景、结果指标和可撤销生命周期。

## 6. 五平面目标架构

五平面是现有 `5+4+1+1` 的产品职责投影，不替代稳定分层契约。

```text
用户与 Agent
    |
体验面: Cockpit / Cockpit UI
    |
控制面: C2G / OMO / MetaOS Policy
    |
织网与执行面: Agora / Runtime / AetherForge / Bus
    |
知识与记忆面: Kairon / KOS / gbrain
    |
协议与进化面: ECOS / Model-driven / L4

Observability 横切所有平面，提供度量、追踪和告警。
```

外部连接织层横切体验、控制、执行和知识平面，但不拥有任务、知识、凭据或运行状态真相。

### 6.1 体验面

- `cockpit` 是唯一人类 CLI、HTTP 和操作控制面。
- `cockpit-ui` 是表现层，不保存其他域的业务真相。
- 子项目 CLI 保留为开发和诊断入口，不作为产品主入口宣传。
- UI 获取不到真实数据时必须显示 unavailable/demo，不得用随机或默认指标伪装运行状态。

### 6.2 控制面

- `c2g` 只负责把意图、Pitch 和 Bet 物化为治理输入。
- `omo` 独占任务、债务、审批、证据、执行状态和变更审计。
- `metaos` 收窄为策略、门控和免疫插件，不再拥有第二套任务真相或通用 DAG 状态。
- MetaOS 连续两个季度若没有独立消费者和发布价值，应合并为 OMO policy package。

### 6.3 织网与执行面

- `agora` 只做发现、BOS 路由、代理和跨域通信，不持有领域业务逻辑。
- `runtime` 负责实际执行、沙箱、调度状态、心跳和恢复。
- `aetherforge` 负责模型、凭据、配额、成本、算力节点和 Swarm 计算。
- `bus-foundation` 是内部 Data/Event/Control 基础库，不发展第二套路由或任务系统。
- `mesh-router` 的能力归属 AetherForge，稳定后不再以根目录独立实现存在。

### 6.4 知识与记忆面

- `kairon` 负责采集、解析、结构化、推理和领域知识处理。
- `KOS` 负责可重建索引、检索执行、本体投影和排序。
- `gbrain` 负责持久知识对象、关系、偏好、长期记忆和共享上下文。
- 原始源清单和持久知识对象是权威事实；向量、FTS、本体图等是可重建派生物。
- Kairon 与 gbrain 之间禁止保存互不一致的第二份 canonical document。

### 6.5 协议与进化面

- `ecos` 只拥有协议、MOF、约束、schema 和可执行验证，不反向依赖 L2/L3 业务实现。
- `model-driven` 只负责投影、生成和生命周期 DSL，不持有运行任务状态。
- `l4-kernel` 只负责系统自我模型、域目录、能力边界和演进提案。
- KEMS 从 L4 内核职责降为可冻结、可安装、可移除的领域包。

### 6.6 外部连接织层

External Connection Fabric 统一承接六类外部能力：`SourcePack`、`ResourcePack`、`MethodPack`、
`ToolPack`、`ChannelPack` 和 `ModelPack`。它只拥有描述、准入、路由、健康、来源和生命周期，
不创建第二套任务、权限、证据或持久知识真相。机器契约见
[`external-connection-fabric.yaml`](../.omo/_truth/registry/external-connection-fabric.yaml)，
操作标准见 [`external-connection-fabric.md`](../.omo/standards/external-connection-fabric.md)。

## 7. 项目组合决策

| 组合 | 决策 | 长期边界 |
|---|---|---|
| cockpit + cockpit-ui | 核心 | 唯一人类入口和表现面 |
| agora | 核心 | 唯一 Agent Mesh 与 BOS Router |
| c2g + omo | 核心 | 意图入口与治理状态机 |
| runtime + aetherforge | 核心 | 执行系统与算力系统 |
| kairon/KOS + gbrain | 核心 | 知识处理、索引和持久记忆 |
| ecos | 核心协议 | 元模型、约束、schema、验证 |
| metaos | 收敛观察 | 收窄为 OMO policy plugin |
| model-driven | 收敛观察 | 收窄为生成与投影工具 |
| l4-kernel | 收敛观察 | 自我模型，剥离领域业务 |
| bus-foundation | 内部基础库 | 事件与控制传输原语 |
| observability | 横切基础设施 | 追踪、指标、日志、告警 |
| omo-debt | 合并候选 | 能力并入 OMO 后归档独立仓 |
| mesh-router | 合并候选 | 能力并入 AetherForge Mesh |
| toolbox | 能力供应商 | 通过 Agora/BOS 暴露，不进入核心状态面 |
| KEMS / family-hub | 冻结领域包 | 通过场景激活门后再恢复投入 |

未来十二个月原则上不新增顶层项目。例外必须通过架构评审并证明现有责任方无法承载。

## 8. 三条黄金旅程

### 8.1 J1 工程交付闭环

```text
意图 -> C2G/OMO task -> 独立 worktree -> Agent Workflow
     -> 实施与测试 -> PR -> 合并 -> evidence -> gbrain/KOS 经验回写
```

这是当前最高优先级，因为它已经是系统所有者的真实高频场景，并直接回应“不丢失、不覆盖、
随时提交、独立 worktree、PR 合并”的核心诉求。

退出门槛：连续真实任务均能从意图走到合并和证据，失败可恢复，且无共享主工作区覆盖事故。

### 8.2 J2 知识到行动闭环

```text
代码/文档/资料 -> Kairon 处理 -> gbrain 持久化 -> KOS 检索
              -> 判断/建议 -> OMO task -> 执行 -> 结果回写
```

成功标准不是索引数量，而是知识是否减少查找时间、改善决策并被后续任务复用。

### 8.3 J3 受控多 Agent 协作闭环

```text
可拆任务 -> 独立性判定 -> 多 Agent 分派 -> 独立产物
        -> 汇总验证 -> 冲突检测 -> 人工批准 -> 交付
```

仅用于边界清晰、无共享写入或可分区写入、可独立验收的工作。架构分析、调试、复杂设计和
强耦合改动继续由单 Agent 主导。物理多机保持 deferred，直到真实需求重新触发。

### 8.4 J4 外部知识与能力触达闭环

```text
场景 -> 发现资源 -> 沙箱验证 -> OMO 准入 -> Agora 选择
     -> Workflow Mesh 调用 -> 来源/回执/成本证据 -> 结果回写 -> 方法或路由改进提案
```

J4 的成功标准不是连接数量，而是外部资源是否缩短了决策和交付时间、提高了证据质量，
并且在权限、成本、时效或可用性变化时能够降级、隔离和回滚。

## 9. 受控智能与进化闭环

系统的智能化成熟度按五级递进：

| 级别 | 能力 | 进入条件 |
|---|---|---|
| I1 可调用 | 能力有真实入口并可执行 | 非 mock，端到端 smoke 通过 |
| I2 可评测 | 有数据集、指标和基线 | 质量、成本、延迟可重复测量 |
| I3 可选择 | 能根据上下文选择模型、工具和策略 | 路由决策有解释和置信度 |
| I4 可适应 | 能从结果反馈生成改进提案 | 影子评测优于基线 |
| I5 可进化 | 能灰度晋升新策略并安全回滚 | 人工批准、审计、回滚全部有效 |

标准进化回路：

```text
观察 -> 评测 -> 改进提案 -> 影子运行 -> 人工审批
     -> 灰度发布 -> 证据对比 -> 晋升或回滚 -> 经验入库
```

职责分配：L4 提案，OMO 治理，Runtime 执行，AetherForge 提供算力，Observability 测量，
gbrain 保存经验，ECOS 只在 ADR 批准后更新约束。

B.D.S.K. 后续演进重点不是增加 Persona 文案，而是让四角意见真实读取提案上下文、历史证据、
成本、风险和评测结果，并通过 AetherForge 选择本地或云端模型。固定模板只能标记为 framework shell。

## 10. 36 个月路线图

### Stage A: 真相归一，0-30 天

- 统一根仓远端身份，所有 worktree/submit/merge 明确 root remote。
- 将项目注册表中的派生数量改为生成或校验，不再长期手抄。
- 对齐 current goals、current phase、task registry 和真实执行计划。
- UI 移除误导性随机/默认运行指标，明确 live、stale、demo、unavailable。
- 建立黄金旅程的事件 ID、run ID 和 evidence ID 贯通规则。
- 建立 `scene_id`、`journey_id`、`outcome_metric` 与外部资源 descriptor 的绑定规则。

里程碑 M0：Git、项目注册、当前目标和 UI 状态没有互相冲突的真相。

### Stage B: 工程交付产品化，30-90 天

- Cockpit 提供“新任务、执行、审批、PR、证据、恢复”的单一工作台。
- Agent Workflow 与 worktree/PR 生命周期贯通。
- 交付结果自动写入 evidence，并形成可检索的复盘对象。
- 用真实任务而非测试夹具验证连续闭环。

里程碑 M1：J1 成为日常默认工作方式，端到端成功率和人工介入有稳定基线。

### Stage C: 知识到行动，3-6 个月

- 统一 source manifest、knowledge object 和 derived index 的身份。
- 打通工程知识检索、决策依据、任务创建和结果回写。
- 将外部连接织层 v1 接入 SourcePack、ToolPack、MethodPack 和 ChannelPack 的真实小场景；运行时 descriptor、动态发现、场景准入、能力路由和 Mesh receipt 边界已具备，下一步只激活有真实消费者的连接。
- 建立“被检索、被引用、产生行动、产生结果”的价值链指标。

里程碑 M2：J2 产生可证明的时间节省和知识复用收益。

### Stage D: 受控适应，6-12 个月

- B.D.S.K. 接入真实上下文和评测集。
- AetherForge 根据质量、成本、延迟和数据敏感度选择模型。
- 多 Agent 仅进入已证明正收益的任务类别。
- 建立 shadow、canary、kill switch 和 rollback。

里程碑 M3：智能策略能通过评测证明改进，且任何自动变化都能被拦截和回滚。

### Stage E: 个人智能执行 OS，12-24 个月

- 统一个人知识、偏好、任务、复盘和长期记忆。
- 提供领域包 SDK，使场景扩展不再复制平台内核。
- 以单设备高频体验为优先，再按真实需求扩展设备同步。

里程碑 M4：系统进入每周高频使用，至少两个领域包复用同一核心闭环。

### Stage F: 生态与外溢，24-36 个月

- 根据真实需求推进多设备、私有部署、团队空间和联邦知识。
- 将 GaC、SSOT、BOS、Agent Workflow 和受控进化沉淀为可复制方法。
- 商业化或对外产品化必须由外部复用证据触发，不作为默认前提。

里程碑 M5：核心方法在第二个真实环境中复用，无需复制或分叉平台内核。

## 11. 指标体系

| 维度 | 指标 |
|---|---|
| 用户价值 | 每周成功闭环、结果消费率、节省时间、知识复用率 |
| 产品旅程 | 端到端成功率、步骤数、人工介入、失败恢复时间 |
| 智能质量 | 评测提升、置信度校准、拒答质量、单位任务成本 |
| 运行可靠性 | 可用率、错误率、MTTR、回滚成功率、stale 数据率 |
| 架构收敛 | 顶层入口数、重复 SSOT、跨层反向依赖、独立项目数 |
| 治理效率 | 治理投入占比、规则命中率、误报率、证据自动生成率 |
| 协作收益 | 适用任务数、墙钟收益、冲突率、汇总返工率 |
| 外部连接价值 | 连接激活时间、来源引用覆盖率、外部调用回执率、单位旅程成本、降级恢复率 |

健康分只用于定位风险，不能替代用户价值和端到端旅程指标。

## 12. 风险与止损

| 风险 | 止损机制 |
|---|---|
| 继续扩项目和架构 | 十二个月顶层项目冻结；例外必须有场景激活证据 |
| 治理挤占产品 | 每月审查 70/30 投入；无对应用户旅程的治理项不得升级优先级 |
| 多套状态机并存 | OMO 独占治理状态；MetaOS/Runtime 只持有各自职责内状态 |
| 知识重复和漂移 | canonical object 唯一；索引必须可重建 |
| UI 假绿 | fallback 必须显式 demo/unavailable，禁止随机值表现为 live |
| Agent 并发覆盖 | 独立 worktree、路径 claim、PR 和 branch protection |
| 自动进化失控 | 影子、审批、灰度、kill switch、回滚缺一不可 |
| 外部连接失控或数据泄漏 | descriptor 只存 credential_ref；默认零复制；OMO 准入；数据分级；可隔离和可撤销 |
| 物理多机提前投入 | 保持 deferred，由真实场景重新触发 |
| KEMS 等领域过早建设 | 冻结为领域包，通过场景激活门后恢复 |

## 13. 近期执行入口

近期工作拆为四个可独立交付的任务包：

1. 根仓身份与 worktree/PR 路径修复。
2. SSOT、current goals 与状态时间线归一。
3. 工程交付黄金旅程与 Cockpit 真实状态体验。
4. 外部连接织层 descriptor、Iris 插件发现和场景化准入。

每个任务包的文件边界、Agent Workflow、验收门禁和可直接使用的 Agent 指令见：

[`docs/proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md`](proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md)

## 14. 战略完成定义

本战略不是在 2029 年“建设完所有功能”，而是在系统具备以下稳定能力时完成：

- 用户意图可以通过一条主路径转化为可靠结果。
- 系统能证明结果、记住经验并在失败后恢复。
- 新场景通过领域包扩展，不复制基础设施和状态机。
- 智能策略可以被评测、批准、灰度、晋升和回滚。
- 架构、运行状态、Git 交付和用户体验共享同一事实时间线。

届时 eCOS 才真正从“完整的 AI 操作系统骨架”成为“日常可用、可持续进化的个人智能执行系统”。
