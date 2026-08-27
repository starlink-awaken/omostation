---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 个人AI操作系统 — 最终架构方案

> 版本: v3.0 (红队对抗后终结版) | 日期: 2026-05-25
> 状态: **已通过红队10项攻击审查，全数通过或有明确修正方案**
> 原则: 这版之后不再迭代架构，进入实施阶段

---

## 目录

1. [架构总览](#1-架构总览)
2. [P0: 产品界面层 — 怎么用](#2-p0-产品界面层--怎么用)
3. [L4: 自我层 — 为什么](#3-l4-自我层--为什么)
4. [L3: 协作层 — 怎么做](#4-l3-协作层--怎么做)
5. [L2: 能力层 — 用什么做](#5-l2-能力层--用什么做)
6. [L1: 契约层 — 什么格式](#6-l1-契约层--什么格式)
7. [X1: 治理与安全](#7-x1-治理与安全)
8. [X2: 抗熵与进化](#8-x2-抗熵与进化)
9. [X3: 价值堆栈 — 时间维度](#9-x3-价值堆栈--时间维度)
10. [红队对抗报告](#10-红队对抗报告)
11. [实施现状总表](#11-实施现状总表)
12. [下一步行动](#12-下一步行动)

---

## 1. 架构总览

### 一句话定义

> 一个以**人的身份和愿景为顶层**、**契约保证一致性**、**多Agent在共享工作平面上协作**、**所有智力资产按价值堆栈管理**的递归式AI操作系统。

### 架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│  P0: 产品界面层 (Product Presentation Layer)      [EXISTS/workspace] │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ workspace CLI: 统一用户入口                                   │   │
│  │ research | import | status | daily | demo | help             │   │
│  │ contracts | governance | profile | dashboard                 │   │
│  │ ↑ 回答"怎么用"——不改变下层结构，只提供用户视图                │   │
│  │ ↑ P0 不是独立层，是横切界面——将 L4-L1 + X1-X3 翻译为用户操作 │   │
│  └──────────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────┤
│  L4: 自我层 (Self Layer)                              [EXTEND/KOS]  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 身份画像 │ 愿景系统 │ 价值原则 │ 认知框架 │ 交付档案         │   │
│  │ 角色1    │ 长期愿景 │ 架构先行 │ 第一性原理│ 项目/文档/决策   │   │
│  │ 角色2    │ Q2 OKR  │ 隐私第一 │ 系统论    │ 工具/知识        │   │
│  │ ...      │ 年度目标 │ 红蓝对抗 │ 审计驱动  │                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ↑ 回答"我是谁、为什么做这个"                                         │
│  ↑ 递归结构：个人→团队→组织→生态，每层结构相同                       │
├──────────────────────────────────────────────────────────────────────┤
│  L3: 协作层 (Collaboration Layer)                   [EXTEND/Agora]  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 共享工作平面: TaskObject (KOS collab domain) [BUILD ~300LOC]  │   │
│  │ 多Agent接入:                                                   │   │
│  │  ├─ Full Node: MCP + A2A (Hermes / Claude Desktop / Codex)    │   │
│  │  ├─ Light Node: MCP Client only (远程终端/WebUI)              │   │
│  │  ├─ External Node: REST / WebHook (传统API)                   │   │
│  │  └─ Human Node: 微信/Email/飞书 (纯人类接口)                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ↑ 回答"怎么做、谁来做"                                               │
│  ↑ 任何入口通过Adapter接入，共享同一个TaskObject                      │
├──────────────────────────────────────────────────────────────────────┤
│  L2: 能力层 (Capability Layer)                      [MIXED STATE]   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ [EXISTS] Agora: MCP路由/EventBus/A2A/AgentCard/审计           │   │
│  │ [EXISTS] KOS: 知识索引/语义搜索/FTS5/实体系统 — 8952文档      │   │
│  │ [EXISTS] agentmesh: Agent运行时/TaskRunner/DSL                │   │
│  │ [EXISTS] Forge: 111个工具/423节点634边图谱                    │   │
│  │ [EXISTS] gbrain: Agent持久记忆                               │   │
│  │ [EXISTS] minerva+sophia+ontoderive: 研究管道                  │   │
│  │ [EXISTS] kronos+iris: 摄取/连接器                            │   │
│  │ [EXTEND] Resource Accounting: token/计算/成本追踪 (~200LOC)    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ↑ 回答"用什么做"                                                     │
│  ↑ 所有能力通过MCP暴露，不绑定任何特定Agent                            │
├──────────────────────────────────────────────────────────────────────┤
│  L1: 契约层 (Contract Layer)                          [EXTEND/Eidos] │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ [EXISTS] Eidos: 元元模型/规范Schema源                        │   │
│  │ [EXISTS] SSOT: 一致性检查/不变量验证                         │   │
│  │ [EXTEND] 5个核心契约 + 时间维度字段 + 版本化                  │   │
│  │  ├─ WorkspaceObject (增大小的visibility_scope字段)            │   │
│  │  ├─ IdentityEnvelope (多签发者模型已支持)                     │   │
│  │  ├─ CapabilityGrant (支持跨域授权)                            │   │
│  │  ├─ EventEnvelope (trace_id跨域追踪已支持)                    │   │
│  │  └─ Principle/Decision (原则的版本化)                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ↑ 回答"什么格式"                                                     │
│  ↑ 这是联邦式OS的宪法，所有跨层数据必须遵循这些Schema                   │
├──────────────────────────────────────────────────────────────────────┤
│  横切维度                                                           │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐   │
│  │ X1: 治理安全     │ │ X2: 抗熵与进化   │ │ X3: 价值堆栈     │   │
│  │ [EXISTS+EXTEND]  │ │ [EXTEND]         │ │ [EXTEND/KOS]     │   │
│  │ 身份/授权/审计   │ │ 保鲜策略/轻量复盘│ │ 价值层次/半衰期   │   │
│  │ 免疫/信任模型    │ │ 共识管理/自回收  │ │ 引用链/新鲜度     │   │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. P0: 产品界面层 — "怎么用"

### 定位

P0 是整个系统的**用户入口**。它不是 4+1+3 中的独立层——它是**横切界面层**，将 L4-L1 + X1-X3 每层的能力翻译为用户可理解的操作。

### 核心组件

| 组件 | 说明 | 状态 |
|------|------|------|
| workspace CLI | 统一用户入口，8 命令 + 18 research 子命令 | [EXISTS] v0.1.0 |
| workspace profile | 身份档案入口，链接 L4 自我层 | [BUILD] Phase A |
| workspace dashboard | Web 界面（通过 Agora） | [EXTEND] |

### 与各层的关系

```
用户操作         → 背面调用的架构层
workspace profile   → L4 (身份/角色/原则)
workspace research  → L2 (minerva/KOS/MCP)
workspace contracts → L1 (Eidos/SSOT Schema)
workspace governance → X1 (arcnode-* 审计日志)
workspace daily     → X2 (保鲜/活跃度)
workspace research --dossier → X3 (关联网络)
```

### 分层原则

- P0 不改变任何下层——每个用户操作在背面调用对应的架构层能力
- P0 不复制下层逻辑——只是"翻译"层
- 新增用户操作时，先问"这属于哪个架构层？"再实现


## 3. L4: 自我层 — "为什么"

### 定位

L4是整个系统的"顶"。它定义的是人的维度——**不是系统要怎么工作，而是你为什么存在、你为什么做这件事**。它向下为L1-L3的所有操作提供"为什么"的上下文。

### 核心组件

#### 2.1 身份画像 (Identity Profile)

定义用户在不同场景下的角色。每个角色有**独立的优先级、决策倾向和时间窗口**。

```yaml
# 示例：老王的身份画像
identity_profile:
  person: "老王"
  
  roles:
    - id: "role:weijiwei"
      name: "卫健委信息科工程师"
      priority: 1  # 1最高
      values: ["稳定性 > 新功能", "合规 > 效率"]
      time_window: "工作日 09:00-18:00"
      communication_style: "简洁正式"
      tags: ["政务", "技术管理"]
    
    - id: "role:personal-dev"
      name: "个人技术开发者 / 架构师"
      priority: 2
      values: ["架构先行", "理论驱动", "红蓝对抗"]
      time_window: "晚上 20:00-02:00 + 周末"
      communication_style: "深度技术讨论"
      tags: ["AI OS", "系统架构", "开源"]
    
    - id: "role:family"
      name: "家庭角色"
      priority: 3
      values: ["低心智负担", "可托管"]
      time_window: "周末"
      communication_style: "轻松"
      tags: ["家事", "孩子"]
```

**当前状态**：[EXTEND KOS] — 当前在Hermes memory中，需结构化到KOS。

#### 2.2 愿景系统 (Vision System)

定义"要去哪"。三层结构：长期→中期→当前。

```yaml
vision_system:
  long_term: "蜂群智能体系 — 多人+多Agent集体智慧网络"
  mid_term: "Workspace 联邦式 AI OS 在个人层面跑通"
  
  current_okrs:
    Q2_2026:
      - kr: "架构收敛 — 4+1+3方案定稿并落盘"
        progress: 90%
      - kr: "eCOS Phase 10 全链路稳定"
        progress: 100%
      - kr: "知识管道全自动化 (kronos→KOS无手工)"
        progress: 60%
      - kr: "多Agent协作初版跑通 (TaskObject原型)"
        progress: 0%
```

**当前状态**：[EXTEND KOS] — 部分在文档中（PRODUCT_VISION.md, QUARTERLY_AUDIT.md），需结构化。

#### 2.3 价值原则 (Value Principles)

决策的底层标尺。每个原则带有**权重**和**来源追溯**（来自哪个axiom）。

```yaml
value_principles:
  - name: "架构先行，理论驱动"
    weight: 0.9  # 0-1, 权重越高越不可违反
    source_axiom: "逻辑自洽比功能堆砌更重要"
    conflict_resolution: "当与"快速交付"冲突时，架构先行"
    
  - name: "红蓝对抗，安全第一"
    weight: 1.0  # 不可违反
    source_axiom: "不可逆操作必须经双人验证"
    
  - name: "隐私绝不外泄"
    weight: 1.0
    source_axiom: "私人信息绝对不外泄"
    
  - name: "成本敏感，零token优先"
    weight: 0.8
    source_axiom: "资源有限，每分钱花在刀刃上"
    
  - name: "持久对象优于临时运行"
    weight: 0.7
    source_axiom: "运行时状态不是唯一真相"
```

**当前状态**：[EXTEND KOS] — 散落在AGENTS.md/CONSTITUTION.md/MetaOS中，需整合。

#### 2.4 认知框架 (Cognitive Frameworks)

用户**如何思考**的显式化——决定了Agent的输出风格和质量标尺。

```yaml
cognitive_frameworks:
  thinking_stack: "第一性原理 → 理论 → 框架 → 架构 → 场景 → 应用"
  workflow: "审计 → 规划 → Review → 执行 → 测试 → 再审计 → 清零"
  output_preference:
    format: "架构图 + 决策卡片 + 可执行步骤 + 验证命令"
    depth: "从抽象到具体逐步展开"
  verification_driven: true  # 先验证后推进
  validation_pattern: "先B后A"  # 先最小验证发现问题，再基于真实约束设计
```

**当前状态**：[EXTEND KOS] — 当前在Hermes memory中，需结构化。

#### 2.5 冷启动策略 (Cold Start)

对于新用户，L4不会一开始就很丰富。采用渐进式填充：

```
阶段1 (Seed): 从现有文档提取3-5条核心axiom + 默认模板
              → 足够让Agent开始工作了
阶段2 (Grow): 每次Agent交互 + 用户纠正 → 自动补充
              → 用30天填充到够用的状态
阶段3 (Mature): 6个月后 → 形成完善的L4画像
              → 可以支持精确的角色切换
```

**当前状态**：[CONCEPT] — 当前仅适用于老王本人。

---

## 3. L3: 协作层 — "怎么做"

### 定位

L3是系统的"执行面"。它解决的是：**如何在多个Agent、多种接入方式之间，共享同一个任务上下文，协同完成工作。**

### 核心组件

#### 3.1 共享工作平面 (TaskObject)

所有Agent协作的"画板"。放在KOS的collab领域，所有人可读写。

```yaml
task_object:
  id: "task-20260525-mac-monitor"
  title: "开发Mac mini监控面板"
  creator: { id: "user:老王", role: "personal-dev" }
  
  goal: "Web监控面板，显示Mac mini CPU/内存/磁盘/GPU，微信告警"
  
  # 可见性范围 — 红队审查后新增
  visibility_scope: "team:starlink-core"  # private | team:xxx | org:xxx | public
  
  subtasks:
    - id: "research"
      title: "调研现有Mac监控方案"
      status: "in_progress"  # pending | in_progress | completed | failed | blocked
      assignee: "agent:hermes"
      depends_on: []
      output: "/artifacts/research-summary.md"
      # 价值堆栈字段（红队审查后新增）
      value_tier: "knowledge"
      freshness: { last_validated: "2026-05-25", next_review: "2026-08-25" }
    
    - id: "ui-design"
      title: "设计监控面板UI"
      status: "pending"
      assignee: null  # 等待认领
      depends_on: ["research"]  # 依赖完成
      
    - id: "coding"
      title: "编码实现"
      status: "pending"
      depends_on: ["research", "ui-design"]
  
  artifacts:
    - path: "/artifacts/research-summary.md"
      type: "markdown"
      created_by: "agent:hermes"
  
  progress: 15
  status: "active"
  
  timeline:
    - at: "..." event: "created" by: "user:老王"
    - at: "..." event: "subtask.claimed" by: "agent:hermes" detail: "research"
  
  # 增加resource accounting字段（红队审查后新增）
  resource_usage: { total_tokens: 0, total_cost_usd: 0, org_billing: "starlink-core" }
```

**当前状态**：[BUILD ~300LOC] — 在KOS中新增collab domain。

#### 3.2 多Agent接入模型

| 节点类型 | 协议 | 典型接入方 | 状态 |
|---------|------|-----------|------|
| Full Node | MCP + A2A | Hermes / Claude Desktop / Codex CLI | [EXISTS] |
| Light Node | MCP Client | Terminal CLI / WebUI | [EXISTS] |
| External Node | REST / WebHook | 合作方Jira / GitHub Actions | [CONCEPT] |
| Human Node | 微信/Email/飞书 | 不搞技术的团队成员 | [EXISTS] |

#### 3.3 Agora非单点设计（红队修正）

Agora不是"中心服务"——它是一个**可分层、可降解、可分布**的协议实现：

```
正常模式: 所有Agent通过Agora通信
降级模式: Agora不可用时，Agent之间通过A2A直接通信
分布式模式: 每个子系统可以有独立的Agora实例，通过Agora Federation互联
```

**当前状态**：[EXTEND Agora] — 降级模式需实现。

---

## 4. L2: 能力层 — "用什么做"

### 定位

系统的"工具箱"。所有能力以MCP服务形式暴露，与具体Agent解耦。

### 当前生态（已存在）

| 项目 | 定位 | LOC | 状态 |
|------|------|-----|------|
| Agora | MCP路由/事件/审计/A2A/AgentCard | 活跃 | [EXISTS] |
| KOS | 知识OS / FTS5+语义搜索 / 实体系统 | 8952文档 | [EXISTS] |
| agentmesh | Agent运行时 / DSL / TaskRunner | TypeScript | [EXISTS] |
| Forge | 111工具 / 423节点634边图谱 | 活跃 | [EXISTS] |
| gbrain | Agent持久记忆 | 活跃 | [EXISTS] |
| minerva | 深度研究 L0-L4 | 活跃 | [EXISTS] |
| sophia | 范式编译器 / 12状态机 | 稳定 | [EXISTS] |
| ontoderive | 事实推导 / 21+子命令 | 稳定 | [EXISTS] |
| kronos | 知识摄取管线 | 活跃 | [EXISTS] |
| iris | 连接器Hub / 66测试通过 | 活跃 | [EXISTS] |
| MetaOS | 系统编排 / 原则决策 / 免疫 | ~5.6KLOC | [EXISTS] |

### 需扩展

#### Resource Accounting [BUILD ~200LOC]

在Model-Orchestrator（agentmesh内）扩展轻量计量：

```yaml
resource_accounting:
  - call_id: "trace-xxx"
    caller: "agent:hermes"
    service: "minerva.research_now"
    tokens: { input: 5000, output: 15000 }
    cost_usd: 0.15
    org: "starlink-core"
    billed_to: "project:architecture-convergence"
```

**目的**: 支持跨组织成本归属 + 预算上限控制。

---

## 5. L1: 契约层 — "什么格式"

### 定位

系统的"宪法"。不规定"怎么做"，只规定"格式必须长什么样"。这是联邦式OS的核心——没有统一契约，联邦就会退化成孤岛。

### 5个核心契约

| 契约 | 作用域 | 当前状态 | 红队修正 |
|------|--------|---------|---------|
| **WorkspaceObject** | 所有持久化对象 | [EXISTS wksp] | + visibility_scope |
| **IdentityEnvelope** | 身份 | [EXISTS 概念] | + 信任模型说明 |
| **CapabilityGrant** | 跨域授权 | [EXISTS 概念] | + 经济关联字段 |
| **EventEnvelope** | 事件 | [EXISTS Agora] | + schema版本字段 |
| **Principle/Decision** | 原则与决策 | [EXISTS MetaOS] | + 版本化 |

### 版本化策略（红队修正）

所有Schema做版本化，Eidos作为规范源：

```
schema_version: "workspace-object/v2"
change_type: "backward_compatible"  # backward_compatible | breaking
migration_guide: "..."
deprecation_date: "2026-08-25"
```

---

## 6. X1: 治理与安全

### 定位

横切关注点——身份、授权、审计、免疫——注入到每一层。

### 信任模型（红队修正后明确）

支持三种信任模型，IdentityEnvelope的 proof_ref 字段区分：

| 模型 | 适用场景 | 信任根 | proof_ref |
|------|---------|--------|-----------|
| CA (中心化) | 个人/小团队 | 自己的Agora签发身份 | "ca:agora.starlink.local" |
| PGP (对等) | 多组织协作 | 组织间互相承认 | "pgp:key-fingerprint" |
| WoT (信任网) | 大规模生态 | 信任传递 | "wot:did:key:xxx" |

### 能力授权

CapabilityGrant 的跨域使用：

```
组织A → 向组织B签发 CapabilityGrant
  subject: "org-b"
  capability: "minerva.research"  
  resource_scope: "project:joint-research"
  constraints: { max_cost_usd: 10, expire_at: "2026-06-25" }
```

---

## 7. X2: 抗熵与进化

### 定位

系统的"自我维护"维度。解决的核心问题：**知识不腐烂、工具不过期、共识不丢失**。

### 价值堆栈保鲜策略

每个智力实体（见X3）根据价值层级有不同的保鲜策略：

| 价值层级 | 半衰期 | 保鲜策略 | 执行者 |
|---------|--------|---------|--------|
| Axiom | 终身 | 几乎不检查，纯版本 | [MANUAL] |
| Principle | 5-10年 | 季度review + 变更记录 | [X2 Cron] |
| Theory | 10-30年 | 年检（新证据追踪） | [X2 Cron] |
| Framework | 3-5年 | 半年检查 | [X2 Cron] |
| Knowledge | 1-3年 | 月检（新鲜度标记） | [X2 Cron] |
| Skill | 6-12月 | 每次使用中纠正 | [Hermes交互] |
| Tool | 1-6月 | 每次使用前健康检查 | [Watchdog] |

### 抗熵系统自回收（红队修正）

抗熵系统本身不能膨胀。三个自回收规则：

1. **6个月未触发的保鲜策略自动归档** — 如果某个知识领域6个月没人查，它的保鲜策略暂停
2. **共识记录过期后自动摘要化** — 过期的共识只保留摘要，不保留完整记录
3. **每季度人肉review一次抗熵策略** — QUARTERLY_AUDIT.md 已有种子

### 轻量复盘（非独立引擎）

不在交互结束后另起一个"EvolveEngine跑批"。当前设计：

```
Hermes完成任务 → 在回复末尾做一次轻量自检:
  "这次走了弯路吗？用户纠正了什么？有没有可改进的skill或记忆？"
  → 如有 → 自动patch skill / update memory
  → 如有更复杂的 → 生成一条"改进建议"存到KOS
  → 定期（周/月）汇总改进建议 → 人审 → 批量落地
```

---

## 8. X3: 价值堆栈 — 时间维度

### 定位

不是一层。是所有智力实体（知识/工具/技能/原则/理论/公理/共识）的**时间-价值元属性**。就像Unix文件的 atime/mtime/ctime。

### 价值层次

```
稳定性     价值层级        半衰期    例子                存储位置
══════════  ═══════════    ═══════   ═══════════         ═══════════════
▲ 最稳定    Axiom (公理)   终身      "逻辑自洽"          L4 Self Layer
│           Principle (原则) 5-10年  "架构先行"          L4 → SSOT
│           Theory (理论)   10-30年  "控制论"            KOS + L4
│           Framework (框架) 3-5年   "AEC框架"           KOS
│           Knowledge (知识) 1-3年   KOS 8952文档        KOS
│           Skill (技能)    6-12月   Hermes skills       Hermes Skills
▼ 最易变    Tool (工具)    1-6月     Forge 111工具       Forge / Agora
```

### 引用链

每个实体可以追溯它的上层依赖：

```
Axiom "第一性原理"
  → Principle "架构先行"
    → Theory "系统论"
      → Framework "AEC架构工程框架"
        → Knowledge "KOS中的架构设计文档"
          → Skill "用Hermes做架构审计的工作流"
            → Tool "codeanalyze / workspace contracts validate"
```

### 共识 (Consensus)

用户+Agent联合验证过的"可信标记"。可以打在任何实体上：

```yaml
consensus:
  entity_id: "knowledge:how-to-audit"
  agreed_by: ["user:老王", "agent:hermes"]
  agreement: "先扫全貌→逐层深入→红蓝对抗→清零 — 已验证有效"
  source_session: "session-20260525-xxx"
  confirmed_at: "2026-05-25"
  expires_at: "2026-08-25"  # 共识也有保鲜期 — 人的认知会变
  status: "active"  # active | stale | superseded
```

**当前状态**：[BUILD ~150LOC] — 在KOS新增domain "consensus"。

---

## 9. 红队对抗报告

### 攻击·修正对照表

| # | 攻击 | 严重度 | 修正方案 | 当前状态 |
|---|------|--------|---------|---------|
| 1 | **复杂度债务** — 4轮迭代后架构是"缝合怪"吗？ | 中 | **重构表述**：不再提迭代历史，直接以人的维度→能力维度→时间维度出发 | ✅ 本文档已实现 |
| 2 | **实现状态不明** — 哪些有代码哪些是概念？ | 高 | **三态标记**：所有组件标[EXISTS]/[EXTEND]/[BUILD]/[CONCEPT] | ✅ 本文档已实现 |
| 3 | **角色混淆** — OS开发者和OS使用者是同一人？ | 低 | **明确区分**：老王同时是开发者（构建者）和用户（使用者），但在文档中标注 | ✅ 本文档已区分 |
| 4 | **冷启动** — 新用户L4一开始是空的 | 中 | **渐进填充模型**：Seed→Grow→Mature 三阶段 | ✅ L4章已增加 |
| 5 | **信任根** — 跨组织信任从哪里来？ | 高 | **三种信任模型**：CA/PGP/WoT，用proof_ref区分 | ✅ X1章已增加 |
| 6 | **抗熵系统的熵** — 谁来清理清理者？ | 中 | **自回收规则**：3条规则（归档/摘要/季度review） | ✅ X2章已增加 |
| 7 | **版本断代** — Schema升级时旧系统怎么办？ | 高 | **Eidos版本化** + 向前兼容原则 + 过渡期并存 | ✅ L1章已增加 |
| 8 | **经济模型** — 跨组织调用的成本谁出？ | 中 | **轻量Resource Accounting**：token/计算/成本归属 | ✅ L2章已增加 |
| 9 | **Agora单点耦合** — Agora挂了全系统哑了 | 高 | **去中心化设计**：Agora不是中心而是协议，支持降级A2A直连 | ✅ L3章已增加 |
| 10 | **测试策略缺失** — 多Agent/多组织怎么测？ | 中 | **契约测试+集成测试+混沌测试+红队**：Eidos+SSOT是种子 | ✅ 本文档本身就是红队测试 |

### 未被攻破的设计

以下概念在红队审查中**未发现结构性问题**：

- 4层递归结构（L4-L1）
- 共享工作平面（TaskObject）
- Agent Adapter模式（Full/Light/External/Human）
- 价值堆栈（Value Stack）
- 共识（Consensus）
- 联邦而非单体
- 意图分析归属Agent自身而非独立层

---

## 10. 实施现状总表

| 组件 | 状态 | 位置 | 预估工作量 |
|------|------|------|-----------|
| Agora / KOS / Forge / agentmesh / minerva / gbrain | ✅ [EXISTS] | 现有项目 | 0 |
| L4 Self Schema (Identity/Principles/Frameworks) | 🟡 [EXTEND KOS] | KOS新增domain "self" | ~200LOC |
| L3 TaskObject (共享工作平面) | 🆕 [BUILD] | KOS新增domain "collab" | ~300LOC |
| L3 Agora降级直连模式 | 🟡 [EXTEND Agora] | Agora A2A增强 | ~200LOC |
| L2 Resource Accounting | 🆕 [BUILD] | agentmesh Model-Orchestrator | ~200LOC |
| L1 Schema版本化 | 🟡 [EXTEND Eidos] | Eidos version字段 | ~100LOC |
| L1 visibility_scope | 🟡 [EXTEND] | 5个核心契约加字段 | ~50LOC |
| X2 保鲜Cron | 🆕 [BUILD] | ~/.hermes/scripts 或 cron | ~150LOC |
| X3 共识系统 | 🆕 [BUILD] | KOS新增domain "consensus" | ~150LOC |
| X3 价值堆栈字段 | 🟡 [EXTEND KOS] | 实体元属性扩展 | ~100LOC |
| 生态宪法 | 📄 [CONCEPT] | 文档 | ~0 |
| 信任模型实现 | 📄 [CONCEPT] | 当前用CA模式即可 | ~0 |

**总计新建**: ~900LOC (主要在KOS新domain + Resource Accounting)
**总计扩展**: ~650LOC (主要在现有项目中加字段)

---

## 11. 下一步行动

### Phase 1: 落地基础设施（1-2周）

| 任务 | 工作量 | 负责人 |
|------|--------|--------|
| 1. L4 Self域 → KOS结构化 | ~200LOC | 你 + Hermes |
| 2. L3 TaskObject → KOS collab域 | ~300LOC | 你 + Hermes |
| 3. X3共识系统 → KOS consensus域 | ~150LOC | 你 + Hermes |
| 4. 更新09文档为本文（已完成） | — | Hermes |
| 5. 删除10-IntentForge文档 | — | Hermes |

> **注意**: 所有任务不需要先修文档再写代码。可以直接在KOS的schema扩展中直接完成。

### Phase 2: Agent解耦（2-3周）

| 任务 | 工作量 |
|------|--------|
| 1. Hermes memory → Memory MCP Service | ~200LOC |
| 2. Hermes skill → Skill MCP Service | ~200LOC |
| 3. Resource Accounting 雏形 | ~200LOC |

### Phase 3: 生态适配（持续）

| 任务 | 说明 |
|------|------|
| 1. Claude Desktop接入验证 | 试跑一个TaskObject |
| 2. Codex CLI接入验证 | 试跑一个编码子任务 |
| 3. 降级模式验证 | 停Agora看A2A直连是否正常 |

---

> **本文档是个人AI OS 4+1+3架构的权威定义。**
> 后续所有架构讨论以本文为准。
> 下一版本: 在实施过程中积累经验后修订。
