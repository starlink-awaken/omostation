---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
> [!WARNING]
> **DEPRECATED**: 本文档描述的 4+1+3 架构或旧版 eCOS 映射已过时。请参考最新的 **eCOS v5.0 (5+3+1)** 宪法大纲：`~/Documents/学习进化/2-knowledge/基建架构/phase6-完成化/pat-45-eCOS-v5-architecture.md`。


# 4+1+3 架构全映射

> 日期: 2026-05-28 | 数据来源: 全会话（~10h 扫描 + 实施 + 诊断）
> 历史架构映射参考 / reference only。本文记录旧阶段 4+1+3 架构分析，不是当前项目清单、当前能力计数、当前入口拓扑或当前健康状态 SSOT。
> 当前架构与项目事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、`/.omo/standards/eCOS-v6-Architecture-Alignment.md`。

---

## 架构框架速览

```
P0 — 产品界面层     : 用户怎么用这个系统
L4 — 自我层         : 系统为什么做 (价值观/认知/身份)
L3 — 协作层         : 系统怎么做决策 (多Agent协作)
L2 — 能力层         : 系统用什么做 (工具/模型/技能)
L1 — 契约层         : 什么格式 (Schema/协议/元模型)
X1 — 治理           : 不能做什么 (约束/规则/审计)
X2 — 抗熵           : 怎么保持新鲜 (保鲜/复盘/回收)
X3 — 价值堆栈       : 价值怎么积累 (共识/追溯/半衰期)
```

---

## 一、P0 — 产品界面层

> 用户与系统交互的所有入口

| 项目 | 定位 | 健康度 | 关键数据 | 评估 |
|------|------|:------:|---------|:----:|
| **hermes-webui** | Web 前端 | 🟢 | :8787, ~20 WS 工具 | 稳定，延续即可 |
| **pallas** | CLI 门面 | 🟢 | 7 命令, ~500LOC | 极薄层，正确委派 |
| **gstack** | 浏览器编排 | 🟡 | 20 orchestrator | 已恢复，需标准化 backend 接入 |
| **bos-skill-cli** | 技能探索 TUI | 🟡 | Python, 有测试 | 低活跃，维持即可 |

**P0 评估**: 全覆盖但分散。gstack orchestrator 尚未与 Interceptor/Browser 技能集成。

**升级建议**: gstack orchestrator → Interceptor backend 对接，约 2h。

---

## 二、L4 — 自我层

> 系统的身份、愿景、认知框架。定义了「我为什么存在」

| 项目 | 定位 | 健康度 | 关键数据 | 评估 |
|------|------|:------:|---------|:----:|
| **KOS self** | 身份/愿景/认知 | 🟢 | 222行 api.py + MCP | 核心实现，完整 |
| **metacog** | 元认知理论基座 | 🟡 | 4 domain × 4 应用 | 内容完整，已通过 knowledge_links 对接 |

**L4 评估**: 架构方案中标记为 [CONCEPT] 的 L4 层，实际已经被 KOS 完整实现（角色系统、愿景三层结构、认知框架）。metacog 补充了认知框架的「血肉」。

**知识链接已建**: `kos/domain/self/knowledge_links.yaml` (25 条目)，但尚未被 KOS runtime 消费。

**升级建议**: 让 KOS MCP 的认知框架工具返回时检索 knowledge_links，约 1h。

---

## 三、L3 — 协作层

> 多 Agent 怎么协作、任务怎么分解、共享工作平面

| 项目 | 定位 | 健康度 | 关键数据 | 评估 |
|------|------|:------:|---------|:----:|
| **KOS collab** | TaskObject 共享平面 | 🟢 | 318行 api.py, SQLite CRUD + MCP | 核心实现 |
| **agentmesh phase-lock** | EG5 相位锁定 | 🟢 | 8/8 test, TS 实现 | T14 交付物 |
| **agentmesh PipelineTracer** | 可观测性 | 🟢 | 8/8 test, TS 实现 | T16 交付物 |
| **DigitalBrainOS coord** | 协作模式 | 🟡 | 文档级别 | 补充协作思路 |

**L3 评估**: KOS collab 是核心——TaskObject 的创建/更新/认领/完成全流程可用。但缺少与 agentmesh 运行时的实际集成（collab 定义任务 → agentmesh 执行任务 → collab 追踪进度）。

**升级建议**: 打通 KOS collab → agentmesh 的 Task → Agent 映射。~3h。

---

## 四、L2 — 能力层

> 系统拥有的能力和工具。这是最厚的一层

### 4.1 Agent 编排

| 项目 | 健康 | 关键数据 |
|------|:----:|---------|
| **agentmesh** | 🟢 | 22 MCP tools, 24+ tests, 3 新模块 |
| **agentmesh Gateway** | 🟢 | :3000, 已 fail-closed, API_KEY 已配 |

agentmesh 处于历史最好状态。

### 4.2 知识推导 & 研究

| 项目 | 健康 | 关键数据 |
|------|:----:|---------|
| **ontoderive** | 🟢 | 21 CLI 命令, MCP 5 tools（本次新增） |
| **pallas** | 🟢 | 7 命令（委派给 ontoderive + agora） |
| **sophia** | 🟢 | 12 状态机, 2 编译路径, MCP |
| **minerva** | 🟢 | L0-L4 研究, :8765, MCP 5 tools, 23 tests |

管线完整：pallas(入口) → minerva(研究) → ontoderive(推导) → sophia(编译)

### 4.3 工具 & 图谱

| 项目 | 健康 | 关键数据 |
|------|:----:|---------|
| **Forge** | 🟢 | 111 tools, 423 nodes, MCP 5 tools（本次新增） |
| **gbrain** | 🟢 | 74 MCP ops, 通过 Agora 注册 |

### 4.4 数据摄取

| 项目 | 健康 | 关键数据 |
|------|:----:|---------|
| **kronos** | 🟡 | 5 层 fetch, 3 级 fallback, 测试从 2→91（本次增强）|
| **Iris** | 🟢 | 66 tests, 7 MCP tools, +Telegram connector（本次新增）|

**L2 评估**: 11 个项目中 9 个 🟢，2 个 🟡。是最成熟的层。

---

## 五、L1 — 契约层

> 数据格式、Schema、协议。系统说什么语言

| 项目 | 定位 | 健康度 | 关键数据 |
|------|------|:------:|---------|
| **eidos** | 元模型 Schema 验证 | 🟢 | 5 MCP tools, pipeline:json 消费（本次） |
| **SSOT** | 配置/状态一致性 | 🟢 | 5 MCP tools, 50/50 tests（本次修复） |
| **pipeline:json** | 管线编排协议 | 🟢 | v1.1 正式化（本次） |

**L1 评估**: 契约层首次完整。pipeline:json 从「草案」变为「v1.1 正式」，eidos 和 ontoderive 两端都实现了消费。

---

## 六、X1 — 治理

> 约束、规则、审计、安全。不能做什么

| 项目 | 健康 | 关键数据 |
|:----:|:----:|---------|
| **arcnode scripts** | 🟢 | 17 约束验证脚本 |
| **CI 集成** | 🟢 | pre-commit + Actions |
| **compliance dashboard** | 🟢 | dashboard.html(42约束) |
| **Agora** | 🟢 | 27 MCP tools, degrade 模式已有 |
| **安全** | 🟢 | 5 fail-open → fail-closed（本次）|

**X1 评估**: 从「文档里的概念」→「代码里锁死的制度」。17 条约束 + CI 通道 + 139 smoke tests + API_KEY fail-closed。全系统最稳固的层。

---

## 七、X2 — 抗熵

> 保鲜、复盘、回收。保持系统不腐烂

| 项目 | 健康 | 关键数据 |
|:----:|:----:|---------|
| **freshness cron** | 🟢 | `~/.hermes/scripts/x2-freshness-cron`（本次创建）|
| **SharedBrain zombie audit** | 🟢 | INDEX.md 63 行（本次）|
| **轻量复盘** | 🟡 | 本次复盘已有文档，未嵌入流程 |

**X2 评估**: 保鲜脚本有了但未计划化运行（无 crontab）。复盘流程无自动化。

---

## 八、X3 — 价值堆栈

> 共识、追溯、半衰期。价值怎么随时间累积

| 项目 | 健康 | 关键数据 |
|:----:|:----:|---------|
| **KOS consensus** | 🟢 | L1/L2/L3 三级共识, SQLite 持久化 |
| **PipelineTracer** | 🟢 | 执行追踪, 8/8 test |

**X3 评估**: 共识系统已可用，但价值半衰期/引用链追溯未实现。

---

## 九、Full Layer Map (24 项目)

```
P0 产品界面 (4)
├── hermes-webui (:8787 WebSocket, ~20 tools)
├── pallas (7 CLI commands, ~500 LOC)
├── gstack (20 orchestrators, 已恢复)
└── bos-skill-cli (TUI, low active)

L4 自我层 (2)
├── KOS self/ (222行, identity/vision/cognitive, MCP)
└── metacog (4-domain cognitive knowledge base)
        ↑ knowledge_links.yaml 对接

L3 协作层 (3)
├── KOS collab/ (318行, TaskObject CRUD + SQLite, MCP)
├── agentmesh phase-lock (EG5, TS, 8/8)
└── agentmesh observability (PipelineTracer, TS, 8/8)

L2 能力层 (11)
├── agentmesh (22 MCP, 24+ tests)        ← Agent 运行时
├── ontoderive (21 CLI, 5 MCP)            ← 事实推导
├── pallas (7 cmd, CLI)                   ← 知识入口
├── sophia (12-state, MCP)                ← 符号编译
├── minerva (L0-L4, :8765, 5 MCP)         ← 研究
├── Forge (111 tools/423 nodes, 5 MCP)    ← 工具图谱
├── gbrain (74 MCP ops)                   ← Agent 记忆
├── kronos (91 tests【本次】, CLI)          ← ETL 摄取
├── Iris (66 tests, 7 MCP, +Telegram)     ← 连接器
├── codeanalyze (CLI)                     ← 代码分析
└── bos-skill-cli (TUI)                   ← 技能发现

L1 契约层 (2)
├── eidos (5 MCP, Schema 验证)
└── SSOT (5 MCP, 50/50 tests【已修复】)  ← 本次

X1 治理 (5 组件)
├── arcnode 17 约束验证脚本               ← 本次
├── CI: pre-commit + Actions               ← 本次
├── dashboard.html (42约束可视化)          ← 本次
├── Agora (27 MCP, degrade 模式)           ← 已有
└── 安全: 5 fail-open→fail-closed          ← 本次

X2 抗熵 (2)
├── x2-freshness-cron (scripts)            ← 本次
└── SharedBrain zombie audit                ← 本次

X3 价值堆栈 (2)
├── KOS consensus (L1/L2/L3)               ← 已有
└── PipelineTracer (TS, 8/8 test)          ← 本次

跨层 / 待定:
├── SharedBrain (44 organs, 5 MCP, 🟡)     ← P0+L2 混合
├── MetaOS (39/39 tests, CLI, 🟢)          ← L2 系统编排
├── DigitalBrainOS (Agent schema done)      ← L2+P0 混合
├── ai-tools (Shell collection, 🟡)
├── eCOS (Cognitive scripts, 🟡)
├── gstack (Archived→Restored, 🟡)
```

---

## 十、Gap 总表

### 🔴 无

### 🟡 Medium (6)

| # | 差距 | 涉及 | 工时 | 说明 |
|---|------|------|:----:|------|
| 1 | **gstack orchestrator→Interceptor** | P0 | 2h | orchestrator 定义缺实际 backend |
| 2 | **KOS collab → agentmesh 集成** | L3 | 3h | TaskObject 定义→Agent 执行 未打通 |
| 3 | **KOS self knowledge_links 消费** | L4 | 1h | 认知框架检索未链接 metacog |
| 4 | **SharedBrain DB 备份** | 运维 | 30m | 103M 未备份 |
| 5 | **X2 cron 计划化** | X2 | 30m | freshness cron 未加入 crontab |
| 6 | **Agent deep 修复** | 平台 | 待定 | 0% 成功率 |

### 🟢 已关闭 (此会话中解决)

| 差距 | 原状态 | 关闭方式 |
|------|:------:|----------|
| 17 约束验证 | 🔴 缺失 | ✅ 脚本 + CI |
| pipeline:json | 🔴 草案 | ✅ v1.1 正式 |
| 统一定价 | 🔴 缺失 | ✅ 3 项目 |
| hermes 测试 | ❌ 0 | ✅ 139 |
| SharedBrain MCP | ❌ 无 | ✅ 5 tools |
| Forge MCP | ❌ 无 | ✅ 5 tools |
| ontoderive MCP | ❌ 无 | ✅ 5 tools |
| Legacy 类型扩展 | ❌隔离 | ✅ DigitalBrainOS→agentmesh |
| security | 🔴 fail-open | ✅ fail-closed |
| KOS L4/L3 确认 | 📄概念 | ✅ 代码已实现 |
| agentmesh build | 🟡 部分失败 | ✅ 修复 |
| kronos tests | 🟡 2个 | ✅ 91个 |

---

## 十一、一句话总结

> **4+1+3 架构中 6 层（P0/L4/L3/L2/L1/X1）齐全且运行中，X2 已启动，X3 有实现。**  
> 从「碎片化项目集合」到「有架构共识的系统」的转型，本次会话完成了最后几个关键节点的硬化和验证。
> 
> **如果只做一件事**: 打通 KOS collab → agentmesh Task 集成。这会让整个 L3 协作层从「定义任务」到「执行任务」变成一条完整的链路。
