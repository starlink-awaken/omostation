---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Workspace AI OS 长期总规划（Master Roadmap）

## TL;DR

> **目标**：把当前的 Workspace 从“多项目能力集合”推进为一个 **联邦式 AI 操作系统**：用户从少量入口进入，系统用统一的对象、身份、能力、事件、schema、原则与审计契约来编排个人、家庭、团队和组织的 AI 工作流。
>
> **方法**：坚持 federation + canonical contracts，不做大一统重构；使用 `.omo` 作为长期规划与执行治理中枢，采用 **Master Roadmap + Spec Track + Task Pool** 的混合机制持续推进。
>
> **时间跨度**：建议按 12–18 个月设计，按 6 个主 Phase 执行；每个 Phase 拆成 Sprint、Wave、Task，并支持并行推进。

**最终愿景**
- 一个统一用户入口（`workspace` / SharedBrain / dashboard）
- 一个统一契约层（object / identity / capability / event / schema / principle）
- 多运行时与多服务联邦（Agora / agentmesh / MetaOS / minerva / connectors）
- 多主体协同（个人、家庭、团队、组织、服务、agent）
- 可持续产品化（可发现、可维护、可扩展、可审计、可运营）

**当前最关键判断**
- 系统不缺能力，缺的是 Workspace-level contract/control plane。
- 下一步最重要的不是“再加新功能”，而是把已有能力收敛进统一对象模型、服务 manifest、事件 envelope、身份/能力模型和原则门禁。

**战略周期建议**
- Phase 0：治理与规划操作系统化
- Phase 1：Canonical Contracts Foundation
- Phase 2：Durable Object / Event / Knowledge Unification
- Phase 3：核心产品旅程闭环化
- Phase 4：联邦控制平面与服务治理
- Phase 5：多主体操作系统（个人→家庭→团队→组织）
- Phase 6：生态化、可维护性、可扩展性与运营化

---

## Context

### 当前状态
- 已有多项目体系：`wksp`、`SharedBrain`、`Agora`、`agentmesh`、`MetaOS`、`Eidos`、`SSOT`、`KOS`、`minerva`、`sophia`、`ontoderive`、`kronos`、`iris` 等。
- 已有多份 `.omo` 内部文档沉淀：产品-架构-旅程、治理计划、洞察与路线图、债务与审计。
- 已完成的最新收敛工作：
  - `WORKSPACE_ARCHITECTURE_CONSTITUTION.md`
  - `WORKSPACE_SYSTEM_OVERVIEW.md`
  - `docs/contracts/workspace-object.schema.json`
  - `workspace contracts validate`
  - `workspace contracts export-research`
  - `workspace status` 展示 Architecture Contracts 健康面板
  - 旧 SQLite `research` 表自动迁移 `full_text`

### 已知问题
- 身份语义分散：SharedBrain node identity / Agora tenant+scope / agentmesh capability permissions 并行存在。
- 事件语义分散：Agora event bus / wksp research_events / MetaOS traces 缺统一 envelope。
- schema 与 contract 分散：Eidos / SSOT / CONTRACTS.md / docs/data-flow.md / README 各自为政。
- 产品入口仍不够单一：用户很难理解“哪条旅程从哪里开始”。
- 缺少面向长期迭代的 spec 管理层，`.omo` 有计划文件但还没有统一 spec track。

### 约束
- 不做单体合并。
- 不中断已有联邦项目自治。
- 以 `.omo` 为长期管理中枢。
- 当前仓库未检测到 `openspec/`、`.specify/`、`_bmad/` 等现成 spec framework 目录，因此本规划采用与 `.omo` 兼容的自定义 spec 机制。

---

## Work Objectives

### Core Objective
建立一个从当前状态通向最终 AI OS 愿景的长期总规划，统一战略、架构、产品、场景、用户旅程、治理和执行节奏，并把后续所有重大能力建设都纳入 `.omo` 的持续规划体系。

### Concrete Deliverables
- 一份唯一主计划：`.omo/plans/workspace-ai-os-master-roadmap.md`
- 一套 `.omo/specs/` spec track 机制设计
- 一套 Phase / Sprint / Wave / Task 的可执行长周期路线图
- 一份缺失能力/债务/增强项矩阵
- 一套长期治理与回顾机制

### Definition of Done
- [ ] 有单一主计划文件，覆盖战略/战术/执行层。
- [ ] 有清晰的最终愿景、边界、原则、约束、成功指标。
- [ ] 有场景矩阵与用户旅程矩阵。
- [ ] 有 architecture target state 与 control plane 设计方向。
- [ ] 有 6 个以上 Phase，且每个 Phase 至少拆到 Sprint / Wave / Task。
- [ ] 有缺失功能与技术债的显式工作流。
- [ ] 有 `.omo` 下可持续迭代的 spec 机制与治理节奏。

### Must Have
- 单一主计划，不再拆成多个互相竞争的“主计划”。
- Roadmap 与现有 `.omo` 文档兼容。
- 任务粒度至少达到能被执行代理认领的程度。
- 同时覆盖产品与架构，不做纯技术路线图。

### Must NOT Have
- 不把所有项目合并成一个大仓内单体平台。
- 不把长期规划写成仅有口号的愿景文档。
- 不把执行路线写成只到 Phase 层的粗粒度大纲。
- 不引入与现有 `.omo` 体系割裂的重型流程工具作为硬前提。

---

## 目标 operating model

### 1. Master Roadmap（唯一主计划）
- 文件：`.omo/plans/workspace-ai-os-master-roadmap.md`
- 作用：长期方向、Phase/Sprint/Wave/Task 全景视图、跨轨道依赖、优先级与门禁

### 2. Spec Track（中期变更控制）
- 建议目录：`.omo/specs/<track>/`
- 每个 track 包含：
  - `SPEC.md`：为什么做、做什么、不做什么、验收
  - `DESIGN.md`：架构与接口设计
  - `TASKS.md`：按 Wave 拆分的任务清单
  - `DECISIONS.md`：关键决策与取舍
  - `VERIFY.md`：验证记录与 evidence 路径

### 3. Task Pool（短期执行）
- 文件：`.omo/TASK_POOL.md`
- 作用：短周期 ready / in_progress / review / done 的执行编排

### 4. State / Review / Retro
- `STATE.md`：记录当前 Phase、Sprint、关键 blocker
- `AUDIT.md`：记录跨项目缺陷、架构债、流程失真
- `LESSONS.md` / `RETRO*.md`：阶段回顾

### 生命周期
```text
Roadmap item -> Spec track -> Task pool -> Implementation -> Verify -> Retro -> Roadmap refresh
```

---

## 产品面与场景面规划

## 目标产品表面

### 用户入口
- `workspace` CLI：统一命令入口
- SharedBrain：个人/家庭的 runtime home
- Agora dashboard：控制面、状态、服务、对象、事件视图
- 后续 Web / MCP / API 表面

### 系统核心表面
- Contracts：object / service manifest / identity / capability / event / principle
- Research：发起、追问、发布、归档、对比、合并、digest
- Knowledge：检索、关系、图谱、dossier、timeline
- Federation：服务注册、路由、健康、授权、租户、观察
- Governance：原则、决策、例外、审计、弃用、成熟度门禁

## 目标场景矩阵

### S1 个人知识工作台
- 用户快速发起研究、持续追问、整理成果、发布与回顾

### S2 家庭 AI Runtime Home
- SharedBrain 作为家庭事务、计划、知识、提醒、协同的宿主

### S3 小团队研究协作
- 共享研究对象、共享能力、共享服务、共享任务池

### S4 组织级 AI Capability Platform
- 组织可注册服务、定义租户与角色、授予能力、审计决策与事件

### S5 开发者 / Agent 扩展生态
- 新项目/新服务按 manifest 接入；新 agent 按 capability contract 接入

---

## 用户旅程规划

### J1 单人研究闭环（当前优先级最高）
输入主题 → 研究执行 → 结果持久化 → 追问 → 发布 → 回顾 → 再利用

### J2 外部内容导入闭环
导入 URL/文件/connector 内容 → 规范化为 artifact → 进入搜索/研究对象

### J3 契约与状态可观测旅程
查看 status → 看 services / contracts / objects / debt → 定位问题 → 修复 → 验证

### J4 家庭任务与知识协同
家庭成员 / agent / node 在 SharedBrain 中协同，结果进入 Workspace contract layer

### J5 团队/组织多主体旅程
组织建立 tenant / roles / capabilities / services → 对象与事件流转 → 审计与 review

### J6 开发者接入旅程
创建新服务/项目 → 定义 manifest / contract → 注册到 Agora → 验证 → 上线

---

## 架构目标态（Target State）

### Layer 1 — Entry / Home
- `wksp`
- `SharedBrain`
- dashboard / Web

### Layer 2 — Control Plane
- Agora registry / governance / event bus / routing
- Workspace status / contracts / roadmap / specs surfaces

### Layer 3 — Runtime Plane
- `agentmesh`：execution runtime
- `MetaOS`：principle / decision / immune orchestration

### Layer 4 — Workload Plane
- `minerva` / `sophia` / `ontoderive` / `pallas`
- connectors / ingestion / task runtimes

### Layer 5 — Truth Plane
- `Eidos` / `SSOT` / `KOS` / `gbrain`

### Canonical Primitives
- `WorkspaceObject`
- `ServiceManifest`
- `IdentityEnvelope`
- `CapabilityGrant`
- `EventEnvelope`
- `Decision`
- `Principle`
- `SchemaContract`

---

## 缺失能力 / 需要完善的功能

### Contract 方向
- [ ] Service manifest schema 与 CLI
- [ ] Identity envelope schema 与投影
- [ ] Capability grant model 与 issuance/revocation flow
- [ ] Event envelope 统一与跨项目映射
- [ ] Principle / decision gate CLI 或 dashboard surface

### Product 方向
- [ ] 更完整的 `workspace help / doctor / roadmap / spec` 入口
- [ ] status 从“服务快照”升级为“系统运营面板”
- [ ] dashboard 增加 objects / events / contracts / debt / specs 视图
- [ ] 用户旅程从“研究闭环”扩展到家庭/团队/组织闭环

### Maintainability 方向
- [ ] 旧数据库 schema migration 体系化
- [ ] manifest 校验门禁
- [ ] 统一错误码 / 统一 CLI 输出约定
- [ ] 契约测试与集成测试矩阵

### Extensibility 方向
- [ ] 新项目 onboarding 流程
- [ ] connector onboarding 流程
- [ ] agent / MCP tool onboarding 流程
- [ ] deprecation / archive 生命周期机制

---

## Execution Strategy

### 路线设计原则
- Phase 定义方向与门槛。
- Sprint 定义 1–2 周内可交付主题。
- Wave 定义可并行执行单元。
- Task 定义最小可认领工作。

### 并行规则
- 同一 Wave 内任务尽量限制在同一 concern、1–3 个文件或 1 个 spec 模块内。
- 每个 Wave 目标 3–6 个任务，可由多个执行者并行。
- 跨 Phase 只允许少量关键依赖串行，其余通过 contract / manifest / docs 提前解耦。

---

## TODOs

## Phase 0 — Planning OS 化与基线建立（2–3 周）

### Sprint 0.1 — 主计划、Spec 轨道、状态模型落地

#### Wave A（可立即开始）
- [ ] 1. 在 `.omo/specs/README.md` 定义 Spec Track 生命周期（draft/approved/in_progress/review/done/archived）；**输出**：spec 使用规范；**依赖**：无；**验收**：README 说明目录结构、状态流转、各文件职责。
- [ ] 2. 创建 `.omo/specs/templates/SPEC.md`；**输出**：标准 spec 模板；**依赖**：1；**验收**：模板包含 goal / scope / non-goals / acceptance / dependencies / risks。
- [ ] 3. 创建 `.omo/specs/templates/DESIGN.md`；**输出**：设计模板；**依赖**：1；**验收**：模板包含 architecture / interfaces / data / migration / observability。
- [ ] 4. 创建 `.omo/specs/templates/TASKS.md`；**输出**：执行模板；**依赖**：1；**验收**：模板能按 wave/task 组织工作并含状态栏。

#### Wave B（依赖 Wave A）
- [ ] 5. 更新 `.omo/STATE.md`，加入 `phase / sprint / wave / spec_track / blocker / next_review_at` 字段；**输出**：统一状态格式；**依赖**：1；**验收**：STATE 可支持未来阶段推进。
- [ ] 6. 更新 `.omo/TASK_POOL.md` 结构说明，使其与 Spec Track 对齐；**输出**：任务池治理规则；**依赖**：4,5；**验收**：明确 ready / in_progress / review / done / archived 规则。
- [ ] 7. 生成 `.omo/plans/roadmap-governance-cadence.md`，定义周会/phase review/retro 节奏；**输出**：治理节奏文件；**依赖**：5；**验收**：包含每周/双周/月度节奏与输入输出。

### Sprint 0.2 — 基线清点与优先级重排

#### Wave A
- [ ] 8. 为现有项目建立 `project inventory` 表（入口、职责、owner、状态、风险、依赖、用户可见度）；**输出**：新增 inventory 节；**依赖**：无；**验收**：覆盖核心项目群。
- [ ] 9. 生成 `journey inventory` 表（J1-J6 当前成熟度）；**输出**：旅程热力图；**依赖**：无；**验收**：每条旅程有现状/缺口/优先级。
- [ ] 10. 生成 `debt inventory` 表（contract debt / product debt / ops debt / maintainability debt）；**输出**：债务矩阵；**依赖**：无；**验收**：每条债务有 owner、严重级别、建议 Phase。

#### Wave B
- [ ] 11. 定义长期 KPI：journey completion、time-to-first-value、contract coverage、service health、debt burn-down；**输出**：KPI 节；**依赖**：8,9,10；**验收**：每个 KPI 有定义、采集源、review cadence。
- [ ] 12. 选定未来 12 个月的 North Star：`single entry + contract coverage + top 3 journeys complete`；**输出**：north star 文案；**依赖**：11；**验收**：写入主计划与 STATE 基线。

## Phase 1 — Canonical Contracts Foundation（4–6 周）

### Sprint 1.1 — 扩展 Object Contract 到 Service / Identity / Capability

#### Wave A
- [ ] 13. 新建 `docs/contracts/service-manifest.schema.json`；**输出**：服务 manifest schema；**依赖**：Phase 0；**验收**：包含 service id、interfaces、capabilities、deps、health、owner、schema refs。
- [ ] 14. 新建 `docs/contracts/identity-envelope.schema.json`；**输出**：身份 envelope schema；**依赖**：Phase 0；**验收**：覆盖 person/agent/service/node/org/tenant。
- [ ] 15. 新建 `docs/contracts/capability-grant.schema.json`；**输出**：能力授权 schema；**依赖**：Phase 0；**验收**：覆盖 subject、capability、scope、actions、constraints、issuer、revocation。

#### Wave B
- [ ] 16. 在 `wksp/cli.py` 增加 `workspace contracts validate-service-manifest`；**输出**：CLI 子命令；**依赖**：13；**验收**：可校验 JSON 文件。
- [ ] 17. 在 `wksp/cli.py` 增加 `workspace contracts validate-identity`；**输出**：CLI 子命令；**依赖**：14；**验收**：可校验 JSON 文件。
- [ ] 18. 在 `wksp/cli.py` 增加 `workspace contracts validate-capability-grant`；**输出**：CLI 子命令；**依赖**：15；**验收**：可校验 JSON 文件。

### Sprint 1.2 — 现有系统投影到新契约

#### Wave A
- [ ] 19. 为 Agora 当前服务注册记录设计 manifest 投影规则；**输出**：design/spec；**依赖**：13；**验收**：明确 registry → manifest 字段映射。
- [ ] 20. 为 SharedBrain node identity 设计 identity envelope 投影规则；**输出**：design/spec；**依赖**：14；**验收**：明确 node key / UUID / org / tenant 映射。
- [ ] 21. 为 Agora governance scopes 设计 capability grant 投影规则；**输出**：design/spec；**依赖**：15；**验收**：明确 scope/action/resource_scope 映射。

#### Wave B
- [ ] 22. 实现 `workspace contracts export-service-manifest <service>`；**输出**：CLI 导出能力；**依赖**：19；**验收**：生成可回验 JSON。
- [ ] 23. 实现 `workspace contracts export-identity <subject>`；**输出**：CLI 导出能力；**依赖**：20；**验收**：生成可回验 JSON。
- [ ] 24. 实现 `workspace contracts export-capability-grant <subject>`；**输出**：CLI 导出能力；**依赖**：21；**验收**：生成可回验 JSON。
- [ ] 25. 更新 `workspace status`，增加 contract coverage 指标；**输出**：status 面板增强；**依赖**：22,23,24；**验收**：显示 object/service/identity/capability 覆盖度。

## Phase 2 — Durable Object / Event / Knowledge Unification（4–6 周）

### Sprint 2.1 — Event Envelope 统一

#### Wave A
- [ ] 26. 新建 `docs/contracts/event-envelope.schema.json`；**输出**：统一事件 envelope；**依赖**：Phase 1；**验收**：覆盖 id/time/source/type/trace_id/actor/object_ref/payload/schema_ref。
- [ ] 27. 为 `wksp research_events` 定义投影规范；**输出**：mapping spec；**依赖**：26；**验收**：created/published/tagged/archive 等事件统一映射。
- [ ] 28. 为 `agora event_bus` 定义对齐规则；**输出**：mapping spec；**依赖**：26；**验收**：Agora persisted events 可映射到 envelope。
- [ ] 29. 为 `MetaOS trace / principle / decision` 定义 envelope 策略；**输出**：mapping spec；**依赖**：26；**验收**：明确哪些 trace 进入 canonical event plane。

#### Wave B
- [ ] 30. 实现 `workspace contracts validate-event`；**输出**：CLI 子命令；**依赖**：26；**验收**：可校验 event envelope JSON。
- [ ] 31. 实现 `workspace contracts export-research-events <id>`；**输出**：CLI 导出能力；**依赖**：27；**验收**：导出 research 事件数组并通过 validate。
- [ ] 32. 为 Agora 增加 event export adapter；**输出**：spec + task；**依赖**：28；**验收**：明确后续实现路径。

### Sprint 2.2 — Knowledge / Object / Dossier 一体化

#### Wave A
- [ ] 33. 定义 `IngestionArtifact` canonical object；**输出**：schema 或 object subtype 规则；**依赖**：Phase 1；**验收**：能承载 iris/kronos 内容。
- [ ] 34. 定义 `PublishedReport` canonical object；**输出**：schema 或 object subtype 规则；**依赖**：Phase 1；**验收**：能承载 wksp publish 结果。
- [ ] 35. 设计 `workspace research dossier` → canonical relations 规范；**输出**：relation contract 设计；**依赖**：现有 export-research；**验收**：parents/children/publications 全部被结构化。

#### Wave B
- [ ] 36. 为 `workspace search/open/dossier/timeline` 建立统一 object-view API 设计；**输出**：design spec；**依赖**：33,34,35；**验收**：定义 object list/detail/timeline/dossier 读取面。
- [ ] 37. 在 dashboard 规划中增加 Objects / Relations / Events 三联视图；**输出**：产品 spec；**依赖**：36；**验收**：有页面与交互定义。
- [ ] 38. 明确 Eidos/SSOT/KOS/gbrain 在 object plane 中的责任边界；**输出**：architecture note；**依赖**：36；**验收**：不再重复承担相同角色。

## Phase 3 — 核心产品旅程闭环化（6–8 周）

### Sprint 3.1 — 单人研究旅程产品化

#### Wave A
- [ ] 39. 把 J1（单人研究闭环）写成 `.omo/specs/j1-solo-research/SPEC.md`；**输出**：旅程 spec；**依赖**：Phase 0；**验收**：包含 happy path / failure path / acceptance。
- [ ] 40. 设计 `workspace doctor` 命令，帮助用户理解入口、依赖、服务状态、契约状态；**输出**：产品 spec；**依赖**：现有 status；**验收**：明确 UX 和命令结构。
- [ ] 41. 统一 `workspace help / status / demo / contracts / research` 的命令叙事；**输出**：CLI IA 设计；**依赖**：39,40；**验收**：形成统一入口导航模型。

#### Wave B
- [ ] 42. 实现 `workspace doctor` 最小版本；**输出**：CLI 能力；**依赖**：40；**验收**：能给出入口建议、服务建议、契约建议。
- [ ] 43. 为 `workspace demo` 定义分层 demo：research / contracts / dashboard / family；**输出**：产品 spec；**依赖**：41；**验收**：把 30 秒可用提升为多旅程 demo。
- [ ] 44. 为 `workspace status` 增加 action-oriented suggestions（不仅显示状态，还告诉用户下一步做什么）；**输出**：增强 spec/task；**依赖**：40；**验收**：不同状态给出不同建议。

### Sprint 3.2 — 导入、发布、回顾旅程补齐

#### Wave A
- [ ] 45. 把 J2（导入闭环）写成 spec，覆盖 url/file/connector 三类来源；**输出**：旅程 spec；**依赖**：Phase 0；**验收**：有 source normalization 与 artifact 落地路径。
- [ ] 46. 把 J3（契约/状态可观测旅程）写成 spec；**输出**：旅程 spec；**依赖**：Phase 0；**验收**：覆盖 diagnose → route → fix → verify。
- [ ] 47. 规划 publish/report 的 canonical object 与 dashboard 展示；**输出**：产品+contract spec；**依赖**：Phase 2；**验收**：发布产物不再只是文件路径。

#### Wave B
- [ ] 48. 定义 journey telemetry 指标：首次价值时间、导入成功率、发布成功率、回顾频次；**输出**：metric spec；**依赖**：45,46,47；**验收**：每项指标有事件与采集点。
- [ ] 49. 在 `workspace status` / dashboard 中暴露 top journeys 健康度；**输出**：产品 spec；**依赖**：48；**验收**：用户能看到哪条旅程是完整/破损的。

## Phase 4 — 联邦控制平面与服务治理（6–8 周）

### Sprint 4.1 — Service Onboarding 与 Registry 标准化

#### Wave A
- [ ] 50. 建立 `.omo/specs/service-onboarding/SPEC.md`；**输出**：新服务接入规范；**依赖**：Phase 1；**验收**：定义 manifest、health、capabilities、owner、deps、deprecation。
- [ ] 51. 设计 `workspace services list / inspect / validate-manifest`；**输出**：CLI spec；**依赖**：50；**验收**：把 Agora registry 暴露给用户入口。
- [ ] 52. 设计服务成熟度模型：prototype / internal / stable / deprecated / archived；**输出**：governance spec；**依赖**：50；**验收**：每个服务可被归类。

#### Wave B
- [ ] 53. 把 Agora registry 现有服务映射到 `ServiceManifest`；**输出**：迁移任务；**依赖**：22,50；**验收**：核心服务至少 3 个完成映射。
- [ ] 54. 规划服务 deprecation 流程：未使用 30 天自动标记 / review / archive；**输出**：governance spec；**依赖**：52；**验收**：有状态流转与例外机制。
- [ ] 55. 规划服务 onboarding QA：manifest 校验、health 校验、status 可见、journey 可接入；**输出**：验收模板；**依赖**：51,53；**验收**：新服务接入有固定 checklist。

### Sprint 4.2 — Principle / Decision / Exception Gate

#### Wave A
- [ ] 56. 建立 `.omo/specs/principle-gate/SPEC.md`；**输出**：原则门禁 spec；**依赖**：MetaOS / SSOT / Constitution；**验收**：定义 principle source、decision source、exception flow。
- [ ] 57. 规划 `workspace governance review` 命令；**输出**：CLI spec；**依赖**：56；**验收**：能检查 contract coverage、service maturity、principle violations。
- [ ] 58. 设计 `Decision` 与 `Principle` canonical objects；**输出**：contract design；**依赖**：56；**验收**：明确和 MetaOS 的映射。

#### Wave B
- [ ] 59. 把关键治理原则固化到 machine-checkable checks（如单一入口、闭环优先、能力冻结例外等）；**输出**：checker plan；**依赖**：56,58；**验收**：至少 3 条原则可被检查。
- [ ] 60. 规划 dashboard governance 页：principles / decisions / exceptions / debt；**输出**：产品 spec；**依赖**：57,59；**验收**：有页面 IA 与关键交互。

## Phase 5 — 多主体操作系统（8–10 周）

### Sprint 5.1 — 家庭与节点协同

#### Wave A
- [ ] 61. 把 J4（家庭协同旅程）写成 spec；**输出**：journey spec；**依赖**：SharedBrain 现状；**验收**：覆盖 member / node / role / task / memory / artifact。
- [ ] 62. 设计家庭场景的 identity / org / membership contract；**输出**：contract design；**依赖**：14；**验收**：家庭不是隐式 tenant，而是显式实体。
- [ ] 63. 设计 SharedBrain → WorkspaceObject / EventEnvelope 投影；**输出**：integration design；**依赖**：62,26；**验收**：家庭 runtime 数据能回流到 Workspace contract layer。

#### Wave B
- [ ] 64. 规划家庭控制台：home dashboard / today / backlog / memory / runtime health；**输出**：产品 spec；**依赖**：61,63；**验收**：定义最小家庭视图。
- [ ] 65. 定义家庭级 capability grants（谁能看、谁能执行、谁能修改）；**输出**：governance spec；**依赖**：15,62；**验收**：至少 4 类权限模型。

### Sprint 5.2 — 团队/组织协同

#### Wave A
- [ ] 66. 把 J5（团队/组织旅程）写成 spec；**输出**：journey spec；**依赖**：Phase 4；**验收**：覆盖 tenant / org / role / service / audit / artifact。
- [ ] 67. 设计 team workspace object namespace；**输出**：namespace design；**依赖**：WorkspaceObject；**验收**：个人与组织对象不冲突。
- [ ] 68. 设计组织级 capability issuance / revocation 流；**输出**：governance design；**依赖**：CapabilityGrant；**验收**：明确审批、撤销、审计。

#### Wave B
- [ ] 69. 规划组织 dashboard：services / contracts / objects / decisions / audits；**输出**：产品 spec；**依赖**：66,68；**验收**：有最小 enterprise control plane。
- [ ] 70. 定义组织 onboarding 流程：create tenant → register services → assign roles → validate journeys；**输出**：operating playbook；**依赖**：66,68,69；**验收**：可被执行团队按步骤执行。

## Phase 6 — 生态化、可维护性、可扩展性与运营化（持续滚动）

### Sprint 6.1 — Developer / Extension Ecosystem

#### Wave A
- [ ] 71. 把 J6（开发者接入旅程）写成 spec；**输出**：journey spec；**依赖**：Phase 4；**验收**：从新项目到可见服务全链路明确。
- [ ] 72. 提供 `new service / new connector / new agent` 脚手架设计；**输出**：developer tooling spec；**依赖**：71；**验收**：明确模板、manifest、contract、tests。
- [ ] 73. 设计 extension quality gate：contract pass / docs pass / status visible / demo reachable；**输出**：验收标准；**依赖**：71,72；**验收**：接入者能自测。

### Sprint 6.2 — Maintainability / Observability / Release

#### Wave A
- [ ] 74. 定义统一错误码、统一 CLI 输出层级、统一 JSON mode 约定；**输出**：platform convention spec；**依赖**：现有 CONTRACTS；**验收**：跨项目接口一致性提升。
- [ ] 75. 设计 contract regression test matrix；**输出**：测试计划；**依赖**：所有 contract schemas；**验收**：object/service/identity/capability/event 至少各有 smoke path。
- [ ] 76. 设计 observability baseline：service health、journey health、contract health、debt health；**输出**：metric+dashboard spec；**依赖**：KPI；**验收**：四类健康度定义完成。

#### Wave B
- [ ] 77. 设计 deprecation & archival policy for projects/services/commands/specs；**输出**：生命周期治理规则；**依赖**：服务成熟度模型；**验收**：明确标记、冻结、归档、恢复。
- [ ] 78. 设计 quarterly roadmap refresh ritual；**输出**：治理流程；**依赖**：Roadmap + Spec Track + KPI；**验收**：每季度可系统性重排优先级。

---

## Final Verification Wave（规划层）

- [ ] F1. Roadmap Coverage Review：检查本计划是否覆盖架构、产品、场景、旅程、扩展性、维护性、治理、执行节奏。
- [ ] F2. Contract Alignment Review：检查各 Phase 是否围绕 canonical contracts 收敛，而不是重新走向项目孤岛。
- [ ] F3. Journey Completeness Review：检查 top journeys 是否都有对应 spec、指标、产品表面和执行路线。
- [ ] F4. `.omo` Process Review：检查 Master Roadmap + Spec Track + Task Pool 生命周期是否闭环。

---

## Commit / Iteration Strategy

本计划不要求一次性实施。建议执行顺序：

1. 先执行 Phase 0，建立规划操作系统。
2. 再执行 Phase 1 和 Phase 2，完成 contract/control plane 基础。
3. 然后并行推进：
   - 产品旅程（Phase 3）
   - 服务治理（Phase 4）
4. 最后做多主体与生态化（Phase 5–6）。

### 推荐节奏
- 每 2 周一个 Sprint review
- 每个 Wave 完成后更新 `.omo/STATE.md` 与 `.omo/TASK_POOL.md`
- 每个新 track 必须先建 `.omo/specs/<track>/SPEC.md`

---

## Success Criteria

### 3 个月内
- `workspace` 成为用户清晰可理解的单一入口。
- Contract layer 不再只有 object，至少扩展到 service/identity/capability/event。
- `.omo` 下的 spec track 真正启用。

### 6 个月内
- Top 3 journeys（研究、导入、状态/诊断）真正产品闭环。
- Agora/SharedBrain/wksp/MetaOS 在 contract plane 上对齐。
- 服务 onboarding 与治理流程标准化。

### 12 个月内
- 个人 / 家庭 / 团队 / 组织四层主体模型跑通。
- Dashboard 成为真正 control plane，而不只是服务页。
- 新项目/新服务/新 agent 能按 contract/maturity gate 接入。

### 18 个月愿景
- Workspace 成为联邦式 AI OS：
  - 少量入口
  - 统一契约
  - 多运行时
  - 多主体
  - 可审计
  - 可扩展
  - 可维护
  - 可持续演进
