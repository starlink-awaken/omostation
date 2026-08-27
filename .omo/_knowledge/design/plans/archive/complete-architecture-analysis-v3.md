---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# 全架构分析 v3 — 24 项目体系

> 日期: 2026-05-28 | 版本: v3.0

---

## 一、项目全景

### 1.1 总览

```
Runtime Core (2)       MCP Buses (3)           Knowledge Pipeline (5)
  agentmesh 🟢           Agora 🟢                KOS 🟢
  MetaOS 🟢              SharedBrain 🟡          ontoderive 🟢
                          Iris 🟢                pallas 🟢
Data Infrastructure (4)                         sophia 🟢
  eidos 🟢                                       minerva 🟢
  kronos 🟡
  SSOT 🟢               Ecosystem Tools (5)     Dispatched (3)
  gbrain 🟢              Forge 🟢               gstack 🗄️ 待定★
                         hermes-webui 🟢        DigitalBrainOS 🗄️ 待定★
CLI (3)                 codeanalyze 🟢          metacog 🗄️ 待定★
  bos-skill-cli 🟡      ai-tools 🟡
  pallas (同K.Pipeline) eCOS 🟡
  24 projects total
```

### 1.2 新纳入的 3 个项目定位

| 项目 | 原状态 | 核心内容 | 架构层归属 |
|------|--------|---------|-----------|
| **gstack** | 🗄️ 归档 | 浏览器自动化栈 (TypeScript, 20+ orchestrators) | P0 产品交互层 — 浏览器能力 |
| **DigitalBrainOS** | 📄 文档 | 全 OS 开发框架 (agents/schemas/mvp_runtime) | 跨 L4+L3+L2 — OS 抽象层 |
| **metacog** | 📄 文档 | 知识笔记库 (4 domain/4 应用) | 跨 L4+L1 — 元认知理论基座 |

---

## 二、项目深度分析

### 2.1 gstack — 浏览器自动化栈

**当前状态**: 已归档 (`Workspace/_archived/gstack`) | 20个 orchestrator | 无下游依赖 | 可随时恢复

**技术栈**: TypeScript + Node.js (与 agentmesh 一致)

**核心能力**:
- 20 个 orchestrator（见 `agents/orchestrators-index.md`）
- 浏览器自动化（与浏览器交互做端到端验证）
- 可被 Web/CLI 技能调用

**对架构的价值评估**:

目前系统中的浏览器能力由以下技能提供：
- `Interceptor` — 真实 Chrome 自动化（当前首选）
- `Browser` — 无头浏览器自动化
- `BrightData` — 4层渐进抓取（含 CAPTCHA 代理）

**gstack 的差异**: 作为**编排层**而非执行层——它不操作浏览器本身，而是编排 20 种自动化模式（orchestrator）。这是 `Interceptor`/`Browser`/`BrightData` 都不具备的能力。

**融入方案**: P0 产品交互层的「浏览器能力」模式库。

**复活建议**: 🟡 **条件性纳入** — 不立即恢复，但在需要浏览器编排模式时优先复用而非重建。

### 2.2 DigitalBrainOS — OS 开发框架

**当前状态**: 存在但低活跃 | 31 个条目 | agents/ + schemas/ + mvp_runtime/

**核心内容**:
- `AGENTS.md` + `AGENTS.zh-CN.md` — 完整中英文治理文档
- `agents/` — 体系化的 Agent 定义
- `schemas/` — 多 Agent 协作架构的 Schema 定义
- `adapters/` — 适配器模式（Telegram/itchat/飞书等）
- `mvp_runtime/` — MVP 运行时代码
- `coordination/` — Agent 协作模式
- `plans/` — 实施计划

**对架构的价值**: DigitalBrainOS 定义了一个**以元认知/身份驱动一切**的范式——Agent 的能力由身份决定，而身份由统一的 Schema 描述。这与我们目前的架构方案是**互补而非重叠**：
- 我们的架构：Agent → capability → tool → MCP
- DigitalBrainOS：identity → role → agent → adapter → platform

**核心冲突/对齐**: 
- 身份模型：DigitalBrainOS 的身份定义比我们目前的 A1 身份声明更完整（包含 personality/preferences/boundaries）
- Agent 定义：DigitalBrainOS 的 Agent schema 比 agentmesh 的 AgentDefinition 更丰富
- 适配器：DigitalBrainOS 的 adapter 模式（Telegram/飞书等）弥补了我们缺失的外部接入

**融入方案**: 
- L2 能力层 — Agent 定义增强（吸收 DigitalBrainOS 的 schema 进 agentmesh）
- P0 产品层 — 外部平台适配器（复用它已有的 Telegram/飞书 adapter）

**复活建议**: 🟢 **高价值纳入** — 其 Agent schema 可以直接补充 agentmesh 的 AgentDefinition 类型。

### 2.3 metacog — 元认知知识库

**当前状态**: 存在但低活跃 | 13 个条目 | `.kiro` 工具

**核心内容** (4 domain × 4 应用):
- `01-theories/` — 理论层（思维框架、系统模式）
- `02-practices/` — 实践层（应用模板、决策案例）  
- `03-foundations/` — 基础层（神经科学、认知心理学）
- `04-applications/` — 应用层（方法论+案例）

**对架构的价值**: metacog 是**元认知的理论基座**，填补了架构方案中 L4 自我层的「认知框架」深度。

对比 KOS `self/` domain：
- KOS self 定义了「我是谁」（角色/愿景/认知框架的**骨架**）
- metacog 提供了「我是怎么思考的」（认知框架的**血肉**——理论来源、实践案例、心理基础）

**融入方案**:
- L4 自我层 — metacog 作为 KOS `self/` 的**元认知知识库**，提供认知框架的理论基础设施
- L1 契约层 — metacog 的概念可以作为 Eidos schema 的来源

**复活建议**: 🟢 **高价值纳入** — 与 KOS self domain 天然互补。

---

## 三、架构整合框架

### 3.1 更新后的架构拓扑

```
P0 产品交互层
├── hermes-webui (Web) ← gstack (浏览器编排模式) ← 新增
├── CLI: pallas/bos-skill-cli/workspace
└── 外部适配器: ← DigitalBrainOS adapters (Telegram/飞书/微信) ← 新增

L4 自我层
├── KOS self/ (身份/愿景/认知框架骨架)
└── metacog/ (认知框架血肉 — 理论/实践/基础) ← 新增

L3 协作层
├── KOS collab/ (TaskObject 协作平面)
└── DigitalBrainOS coordination/ ← 补充协作模式

L2 能力层
├── agentmesh (Agent 运行时)
└── DigitalBrainOS schema/ (Agent 定义增强) ← 补充定义深度

L1 契约层
├── eidos (元模型/ Schema 验证)
└── metacog metacognition (认知模型概念集) ← 思想来源

X1 治理
├── 17 约束验证脚本
├── arcnode CI
└── DigitalBrainOS AGENTS.md 治理模式 ← 补充治理思路

X2 抗熵
├── freshness cron
└── DigitalBrainOS plans/ ← 战略规划可参考

X3 价值
├── KOS consensus/
└── metacog 案例库 ← 决策追溯的思想来源
```

### 3.2 整合优先级

| 优先级 | 项目 | 动作 | 价值 |
|--------|------|------|------|
| P0 | **DigitalBrainOS agent schema** → agentmesh | 将 DigitalBrainOS 的 Agent schema 定义 merge 到 agentmesh 的 AgentDefinition 类型中 | 身份模型深度提升 |
| P1 | **metacog** → KOS self 知识对接 | metacog 理论/实践作为 KOS self domain 的知识引用 | L4 自我层深度化 |
| P2 | **gstack** → 按需恢复 | 当需要编排化浏览器场景时恢复使用 | 避免重复造轮 |
| P3 | **DigitalBrainOS adapters** → Iris | 复用 Telegram/飞书 adapter 到 Iris 连接器 | 外部接入扩展 |

### 3.3 新体系的完整 Layer-Map

```
Layer     | 传统 OS 类比   | 本架构实现
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0 UI     | 桌面/终端      | hermes-webui + gstack + pallas
L4 内核   | 启动引导       | KOS self + metacog 
L3 进程   | 进程管理       | KOS collab + DigitalBrainOS coord
L2 驱动   | 设备驱动       | agentmesh + ontoderive + minerva + Forge
L1 指令集 | ISA           | eidos + pipeline:json + DigitalBrainOS schema
X1 安全   | 权限管理       | arcnode 17约束 + CI
X2 维护   | 磁盘清理       | freshness cron + DigitalBrainOS plans
X3 审计   | 日志追踪       | PipelineTracer + KOS consensus + metacog 案例
```

---

## 四、全系统 24 项目状态矩阵

### 4.1 按活跃度

```
🟢 活跃 (15)  🟡 低活跃 (6)    🗄️ 归档 (3)
agentmesh      kronos          gstack ◄
MetaOS         bos-skill-cli   AggreResearch
Agora          ai-tools        hermes-self-evol
SharedBrain    eCOS            DigitalBrainOS ◄  
Iris           metacog ◄      
eidos          
ontoderive     
pallas         
sophia         
minerva        
KOS            
SSOT           
gbrain         
hermes-webui   
Forge          
codeanalyze    
hermes scripts
```

### 4.2 本次周期交付总结

从 v2（执行前）到 v3（执行后）的变化：

| 维度 | v2 状态 | v3 状态 |
|------|---------|---------|
| 项目数 | 21 | **24**（+3 新纳入） |
| Critical 差距 | ~20 🔴🟡 | **0** |
| MCP 覆盖 | 8/14 有 MCP | **13/14**（+Forge/ontoderive/SharedBrain） |
| KOS L4/L3/X3 | 概念 | **代码已实现** |
| 治理测试 | 0 | **139** |
| 归档项目 | 2 | **3**（+DigitalBrainOS 归档标记→重新评估） |

---

## 五、下一步行动建议

### 立即可行（1-2 天）

| 动作 | 涉及项目 | 工作量 |
|------|---------|--------|
| 将 DigitalBrainOS Agent schema merge 到 agentmesh types | DigitalBrainOS → agentmesh | ~2h |
| metacog 接入 KOS self 索引 | metacog → KOS | ~1h |
| 更新 AGENTS.md 纳入 3 个项目 | 全局 | ~15min |

### 中期（1-2 周）

| 动作 | 工作量 |
|------|--------|
| DigitalBrainOS adapters → Iris 集成 | ~4h |
| gstack 按需恢复计划 | ~1h（定义即完成） |
| kronos 测试增强 | ~3h |
