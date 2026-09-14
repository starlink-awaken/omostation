---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-04
---
# Architecture Analysis & Requirements Consolidation

## 1. 背景与目的

本需求文档面向 `omostation` 这个根工作区，聚焦其作为“多项目、多语言、多 Agent 协作治理系统”的整体架构与运行模型展开分析。目标不是简单列举目录，而是回答以下核心问题：

- 这个项目的本体是什么？
- 它的主线架构是什么？
- 多 Agent 协作是如何被治理和执行的？
- 哪些组件属于主线能力，哪些属于专项执行/适配层？
- 当前设计中有哪些风险与结构性问题？
- 如何将当前体系收敛成更稳定、更可维护的治理型 Agent OS？

本文档基于仓库内现有架构文档、治理文档、workflow registry、resident runtime、BOS 路由和执行后端实现进行归纳，必要时将“设计声明”与“代码落地”分开判断。

## 2. 参考资料与事实源

### 2.1 根级架构与运营文件
- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/SYSTEM-INDEX.md`
- `docs/project-registry.yaml`
- `ARCHITECTURE.md`
- `docs/architecture/os-operating-pattern-v1.md`
- `docs/architecture/resident-agent-system-v1.md`

### 2.2 Govern / Execution / Workflow 事实层
- `.omo/_truth/registry/agent-workflows/_root.yaml`
- `.omo/_truth/registry/swarm-coordination.yaml`
- `.omo/_truth/registry/workers.yaml`
- `bin/agent-workflow.py`
- `bin/plan/bet-ledger.py`

### 2.3 执行后端与适配层
- `projects/omo/src/omo/resident/execute.py`
- `projects/omo/src/omo/resident/executor.py`
- `bin/gac/orca-worker-start.py`
- `bin/gac/orca-codex-supervisor.py`
- `bin/gac/pi-worker-adapter.py`

### 2.4 能力入口与路由
- `projects/cockpit/src/cockpit/cli.py`
- `projects/agora/etc/bos-services.yaml`
- `projects/omo` 的治理内核与状态交互代码

## 3. 结论判断（核心判断）

### 3.1 这个仓库不是传统应用，而是“治理驱动的 Agent OS”

从架构和治理文件来看，仓库明显不是单体业务应用，而是一个用于知识工程、智能体治理、BOS 服务路由、工作流闭环和运行态审计的统一工作区。其设计目标是：

- 把多 Agent 协作嵌入制度化治理流程中
- 把人工/Agent/系统操作收敛到统一入口
- 用 SSOT 与 registry 维护事实来源
- 用 workflow、claim、verify、closeout 机制控制执行闭环

### 3.2 它的主线架构是统一控制面 + 分层执行

主线架构的定义可以概括为：

- 控制层：workflow + governance + claim/verify/closeout
- 运行时层：resident agent + execution runtime
- 能力层：BOS / CLI / service registry
- 执行层：local / pi-worker / multica / orca 等 backend

这里的关键是：主线不是多个独立的 Agent 系统并列，而是一个统一的控制面对多个执行后端进行治理。

### 3.3 多 Agent 协作不是“随机并发”，而是“流程强约束协作”

系统明确禁止“无序多 Agent 直接共享主树”，并通过以下机制控制协作：

- worktree 隔离
- per-session claim / bounded work surface
- workflow registry 驱动 start / verify / closeout
- swarm coordination 约束
- resident roles 事件驱动

这意味着真实的多 Agent 模型：不是“多个 Agent 自由联动”，而是“统一控制面下，多个角色化 Agent 按流程执行”。

### 3.4 `multica` / `orca` / `pi-worker` 都属于执行后端或适配层，不是系统总控层

从实现代码看：

- `projects/omo/src/omo/resident/execute.py` 中，`multica` 被明确注册为 execution backend；
- `projects/omo/src/omo/resident/executor.py` 中，`multica` 作为一个后端配置存在；
- `bin/gac/orca-worker-start.py` 和 `bin/gac/orca-codex-supervisor.py` 更像 worker adapter / supervisor；
- `pi-worker` 同样是执行适配层的一种实现。

因此，准确分类应该是：

- 主线架构：workflow governance + resident runtime + BOS route + CLI
- 执行适配层：local / pi-worker / multica / orca

### 3.5 当前体系的最大问题：控制面与适配层尚未完全收敛

当前设计已相当成熟，但还没有完全收敛为一个极简统一的运行面：

- 执行后端分叉明显
- 适配器/worker supervisor 多且相互牵连
- 入口和路由并非完全单一
- 设计声明与实现落地仍需对齐

这是现阶段系统的主要结构性风险：它做到了“治理能力强”，但“最简统一面”还在完善中。

## 4. 系统架构全景

### 4.1 统一入口

系统的入口主要有三条：

1. 人类入口：`cockpit` CLI
2. Agent/Governance 入口：`bin/agent-workflow.py`
3. 能力路由入口：BOS / Agora / MCP / service registry

这三者共同构成统一调用系统，而非多个互不相干的工具面。

### 4.2 核心能力层

- `projects/omo`：治理内核，控制 lifecycle、phase、task、debts、audits
- `projects/agora`：BOS / API/service 入口与能力注册
- `projects/cockpit`：统一界面与命令面
- `projects/ecos`：协议/治理/能力桥接与执行协议定义
- `projects/knowledge`：知识工程与场景管理能力

### 4.3 设计和现实的差异

设计文档强调：
- 单控制面
- SSOT-led
- workflow-first
- no duplicate dispatcher
- isolated worktree

实现层真实存在：
- 多个 worker adapter
- 多个执行后端
- 多个任务入口
- 部分 runtime 代码仍相对“框架化”而非完全统一

这意味着：当前项目已经具备治理骨架，但仍需收口到更统一的运行模型。

## 5. 多 Agent 协作机制：真实说明

### 5.1 协作粒度

协作不发生在“自由的群聊式 Agent 行动”中，而发生在以下事实结构中：

- task / run / packet / instruction / verification / receipt
- `bet` 作为计划与价值承诺载体
- workflow 提供运行时语义
- claim 负责责任边界
- verify 负责执行证据收口

### 5.2 协作约束

关键约束包括：

- 不允许直接写 `.omo` 状态，以 broker / CLI / OMO 管理面为准
- 不允许并行 Agents 共享同一主工作树
- 必须执行 workflow 要求的验证闭环
- 任务必须都绑定到真实的 `bet` 或工作流对象

### 5.3 角色模型

Resident Agent / worker 的角色不是“人人都能做所有事”，而是有分工：

- sediment：知识沉淀
- decision：决策/判断
- execute：执行
- monitor：监控
- heartbeat：心跳与存活

这是一种“角色化执行模型”，比普通 Agent 群更接近工作流执行系统。

## 6. 执行后端与适配层分析

### 6.1 local
- 本地只读/轻操作后端
- 适合低风险、审计明确的动作
- 根据实现，effectful action 需要 admitted workflow context，避免直接副作用

### 6.2 pi-worker
- 属于中风险执行后端
- 适合可逆或受约束操作
- 以 `pi-worker.py` 这类 worker adapter 为入口

### 6.3 multica
- 作为托管自动化 agent backend 接入
- 通过 CLI `multica autopilot create + trigger` 执行
- 更适合更高危、可自动化执行的动作
- 实现中明确设置为 high-risk backend

### 6.4 orca
- 属于 worker / supervisor 适配线
- 例如 `orca-worker-start.py` / `orca-codex-supervisor.py`
- 目的是让 worker 能和多个 provider/agent runtime 管理起联系
- 它不是顶层主干设计，它属于专项协同与适配层

## 7. 关键问题与风险

### 7.1 架构收敛风险
- 多个执行后端存在并存，未完全统一 API
- 适配层职责过多，容易出现“功能在多个地方重复实现”

### 7.2 管理面过碎片化
- Governance、workflow、BOS、resident runtime、adapter 彼此存在边界不够清晰的区域

### 7.3 状态可审计性要求高，但实现面仍需统一
- 运行态状态需要严格走 broker / OMO / registry
- 若仍由多入口写状态，容易出现不可追踪的状态漂移

### 7.4 工具适配层可能“侵入主线架构”
- 当适配器越来越多时，它们很容易成为第二控制面
- 这和项目强烈拒绝的“second dispatcher”设计冲突

## 8. 需求定义（本 BET 的需求）

### 8.1 功能需求

1. 建立完整的项目架构分析产出
   - 说明主线架构与专项适配层的区别
   - 解释多 Agent 协作机制的真实运行方式
   - 梳理主线入口、执行后端和治理边界

2. 形成可复用的需求文档
   - 给出统一的项目分析模板
   - 使后续协作和重构都有共识基线

3. 建立结构化的优化方案
   - 明确短期、中期、长期路线
   - 形成统一执行与治理收敛方案

### 8.2 非功能需求

- 可审计性：所有设计结论必须可追溯到源码和文档
- 可维护性：将适配层与主线架构分离
- 可扩展性：后续新增 backend 时遵循统一接口
- 可治理性：允许运行时按受控流程而不是自由扩张

### 8.3 治理需求

- 需求文件必须在工作流环境中生成
- 在 `bet-ledger` 中写入结构化记录
- 必须明确对应的 track、window、write surfaces、verification
- 需求不应绕过 SSOT/registry 事实源

### 8.4 集成需求

- 需要与现有 `AGENTS.md`、`CLAUDE.md`、`docs/SYSTEM-INDEX.md` 等主文档保持一致
- 应与 `bet-ledger` / worktree / workflow 机制保持兼容
- 需与 project-local governance docs 一致，不制造冲突的事实来源

## 9. 目标与验收标准

### 9.1 目标

本 BET 目标是：

- 把当前 `omostation` 的系统性质、主线架构、协作机制和执行后端关系梳理成正式、可复用、可审查的文档；
- 形成一份明确的架构优化方案；
- 将上述结论写入 `bet-ledger`，以便后续执行和 review。

### 9.2 验收标准

交付物满足以下要求：

- 文档明确说明项目是治理驱动的 Agent OS，而不是单应用
- 主线架构与专项适配层已区分
- 多 Agent 协作机制有明确的真实解释
- `multica` / `orca` / `pi-worker` 的定位已说明
- 架构优化方案具备行动路线与优先级
- 文档可被后续工程或设计 review 直接引用
- 对应 `bet` 已写入 ledger，并保持 YAML 完整有效

## 10. 优化建议（总路线）

### 短期（0-30天）
- 收敛 worktree / claim / workflow 规范
- 明确主控制面和适配层边界
- 把执行后端统一成标准执行接口

### 中期（30-90天）
- 统一 `resident` runtime 事件模型
- 压缩 multiple worker adapter 造成的新增入口
- 补齐状态审计与 observability

### 长期（90天+）
- 形成单一的 Agent OS runtime 设计
- 所有执行后端都由同一套治理和 state model 调度
- Advanced capability routing 和 governance 控制面稳定化

## 11. 结论

`omostation` 的真实价值，不在于“有很多工具或多个 Agent 后端”，而在于它已形成一套带治理机制的 Agent OS 核心框架。当前的主要挑战不是功能不全，而是主线架构和专项适配层还未完全收敛，导致系统容易出现“看起来有很多路径，但本质控制面不够简洁”的状态。

因此，正确的优化方向不是继续堆更多工具，而是收敛到统一控制面、统一执行接口、统一状态审计、统一能力路由。

## 12. 关联文件

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/SYSTEM-INDEX.md`
- `docs/project-registry.yaml`
- `ARCHITECTURE.md`
- `docs/architecture/os-operating-pattern-v1.md`
- `docs/architecture/resident-agent-system-v1.md`
- `projects/omo/src/omo/resident/execute.py`
- `projects/omo/src/omo/resident/executor.py`
- `projects/cockpit/src/cockpit/cli.py`
- `projects/agora/etc/bos-services.yaml`
- `bin/agent-workflow.py`
- `docs/plans/3y-bet-ledger.yaml`
