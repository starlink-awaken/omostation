---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# OpenHuman vs Workspace — 全面对标分析与蓝图

> 日期: 2026-05-28 | 参考: OpenHuman v0.53.22 (GPL-3.0) | 我们的架构 v3.1 (8.8/10)

---

## 一、总览对比

| 维度 | OpenHuman | Workspace | 谁领先 |
|:----:|:---------:|:---------:|:------:|
| **核心理念** | 个人 AI 超级智能桌面助手 | 个人 AI 操作系统 (4+1+3) | — |
| **架构完整性** | 无分层概念 | 六层治理 (P0/L4/L3/L2/L1/X) | 🟢 我们 |
| **代码规模** | Rust 69.4% + TS 26.6% | Python 13项目 + TS 5项目 | — |
| **测试** | 未公开 | 16,676+ 测试 | 🟢 我们 |
| **安全** | 未详细讨论 | fail-closed + 21 验证 | 🟢 我们 |
| **运维** | 无独立运维层 | hermes-ops 21 tools | 🟢 我们 |
| **连接器** | 118+ OAuth 集成 | Iris 2 个 | 🔴 OpenHuman |
| **桌面呈现** | 有脸/会说话/能进会议 | 无 | 🔴 OpenHuman |
| **Token 优化** | TokenJuice 压缩 80% | 无 | 🔴 OpenHuman |
| **记忆系统** | Memory Tree + Obsidian | KOS + gbrain + SharedBrain | 🟡 平手 |
| **行为采集** | 自动同步+实时摄入 | PipelineTracer (仅执行追踪) | 🔴 OpenHuman |
| **自我认知** | 无 | KOS self (L4) 角色/愿景 | 🟢 我们 |
| **协作模型** | 单用户 | KOS collab 多 Agent (L3) | 🟢 我们 |
| **协议标准** | 自定义 | MCP 标准 (13/14) | 🟢 我们 |

---

## 二、逐维深度分析

### 2.1 记忆系统 — 🟡 平手，各有千秋

| 特征 | OpenHuman | Workspace |
|:----:|:---------:|:---------:|
| 存储引擎 | SQLite (单库) | SQLite 多库 (ops/SharedBrain/KOS/gbrain) |
| 知识图谱 | Obsidian .md 文件 | KOS self/collab/consensus + eidos Schema |
| 记忆树 | Memory Tree (≤3000 token 片段) | 无树结构，按 domain 分表 |
| 实时映射 | 每个行为同步到记忆树 | 通过 pipeline:json 链式传递 |
| 学习能力 | AI 消化所有输入数据 | KOS 认知框架 + metacog 理论基座 |

**差距**: OpenHuman 的 Memory Tree 把数据压缩到 ≤3000 token 片段，适合 LLM 消费。我们散落在多个 SQLite 库中，没有统一的「记忆片段化」机制。

### 2.2 连接器生态 — 🔴 OpenHuman 绝对领先

```
OpenHuman:    Gmail Notion Slack GitHub Stripe Calendar Drive Linear Jira + 108 more
              == 118+ 连接器

Workspace:    Obsidian Telegram
              == 2 连接器

差距: 59x
```

这不是一个可以通过「再写一个 MCP server」来解决的问题。OpenHuman 投入了大量工程精力为 118 个服务实现 OAuth 集成。我们的路径应该是：
- 优先补充 3-5 个高频中文生态连接器（微信/钉钉/飞书/邮件/日历）
- 中长期通过 Iris 的 connector 架构 + community 贡献扩展

### 2.3 桌面呈现 — 🔴 OpenHuman 独有，我们完全缺失

OpenHuman 的 Agent 不是对话框里的文字——它有脸、会说话、能以真实参与者身份进入 Google Meet。这是「AI 不是你问它答的对话框，而是一个常驻同事」的具身化实现。

| 能力 | OpenHuman | Workspace |
|:----:|:---------:|:---------:|
| 桌面形象 | ✅ 有脸，Live2D | ❌ |
| 语音 | ✅ STT + TTS | ❌ |
| 视频会议 | ✅ Google Meet 参与 | ❌ |
| 常驻感知 | ✅ 你没打字时也在思考 | ❌ (ops 定时轮询) |
| 用户体验 | 看得见的 Agent | 命令行 + Web 仪表板 |

**这是最大的产品差距。** 我们在架构层面做得更好，但在「让用户感知到 AI 存在」这一点上，OpenHuman 领先了一个时代。

### 2.4 Token 优化 — 🔴 OpenHuman 独有

TokenJuice 把 HTML→Markdown、长 URL→短 URL、非 ASCII 清理 —— 降低 80% token 消耗。我们没有任何 token 优化层。

```
影响: 假设你每天和 agentmesh 进行 100 次 LLM 调用，
     有 TokenJuice: 消耗 20K tokens
     无 TokenJuice: 消耗 100K tokens
     月差: 30 万 tokens / 月
```

### 2.5 行为采集 — 🔴 OpenHuman 领先

| 通道 | OpenHuman | Workspace |
|:----:|:---------:|:---------:|
| 邮件 | ✅ 自动同步 | ❌ |
| 日历 | ✅ | ❌ |
| 聊天 | ✅ Slack | ❌ (微信通过 Iris 计划中) |
| 代码 | ✅ GitHub/Lint | ✅ PipelineTracer (仅执行) |
| 文档 | ✅ Notion/GDrive | ✅ (obsidian connector) |
| 网页浏览 | ✅ (自动抓取) | ❌ |

OpenHuman 采集的是「你日常生活的数据流」，我们采集的是「代码执行的过程」。前者覆盖面是后者的 100x+。

### 2.6 安全治理 — 🟢 我们全面领先

| 维度 | OpenHuman | Workspace |
|:----:|:---------:|:---------:|
| 认证 | (未详细描述) | fail-closed + API_KEY + 集中 Secret |
| 约束 | 无 | 21 条 arcnode 验证 + pre-commit CI |
| 审计 | 无 | ops_events + ops_trace 全链路 |
| 运维 | 无 | hermes-ops 21 tools |
| 红队 | (未提及) | ✅ 5 fail-open→fail-closed 已修复 |

这是 Workspace 最大的差异化优势——我们不只是「能做什么」，更是「不能做什么」。

---

## 三、学习清单：OpenHuman 的 6 个可采长项

| # | 学习项 | 影响 | 实施难度 |
|:--:|--------|:----:|:--------:|
| **1** | **连接器规模化** (118→？) | 🔴 数据入口决定系统上限 | 高 (需 OAuth/API key 管理) |
| **2** | **Token 压缩层** | 🟡 LLM 成本降低 80% | 中 (~200LOC Python) |
| **3** | **行为采集管线** | 🔴 缺少「拉→推」的数据基础 | 中 (Iris 扩展) |
| **4** | **桌面 Agent 呈现** | 🟡 用户体验差 10x | 高 (前端+语音) |
| **5** | **Memory Tree 片段化** | 🟡 记忆结构更适合 LLM | 中 (~300LOC Python) |
| **6** | **20 分钟自动同步** | 🟡 从「被动查询」到「主动消化」 | 中 (ops cron 扩展) |

---

## 四、蓝图：Phase O — OpenHuman 对标迭代

### 总体目标

> 不复制 OpenHuman，而是**吸收其最精华的 6 个设计理念**，融入我们的 4+1+3 架构。

### Sprint O1: 数据入口扩展 (连接器)

| 任务 | 内容 | 工时 |
|:----:|------|:----:|
| O1.1 | Iris 新增 **邮件连接器** (IMAP) | 2h |
| O1.2 | Iris 新增 **日历连接器** (CalDAV/iCal) | 2h |
| O1.3 | Iris 新增 **浏览器行为连接器** (Chrome History) | 2h |
| O1.4 | 连接器 OAuth/API key 管理 (Reuse Secret 架构) | 1h |

### Sprint O2: 智能能力增强

| 任务 | 内容 | 工时 |
|:----:|------|:----:|
| O2.1 | **Token 压缩层** (`hermes-ops token_compressor.py`) | 2h |
| O2.2 | **Memory Tree 片段化** (KOS memory_card.py) | 3h |
| O2.3 | **自动同步循环** (ops cron: 每 20 分钟从 Iris 入口拉取) | 1h |

### Sprint O3: 智能推送 (拉→推)

| 任务 | 内容 | 工时 |
|:----:|------|:----:|
| O3.1 | KOS self **行为模式学习器** (pattern_learner.py) | 4h |
| O3.2 | **智能推送规则生成** (从 behavior patterns 自动生成) | 2h |
| O3.3 | hermes-ops **推送通知** (透过已有告警通道) | 1h |

### Sprint O4: 呈现层 (桌面 Agent)

| 任务 | 内容 | 工时 |
|:----:|------|:----:|
| O4.1 | 桌面 Dashboard 升级 → **桌面 Agent 面板** | 3h |
| O4.2 | 语音 TTS 集成 (通过现有 ElevenLabs skill) | 2h |

### 总工时: ~26h | 最大并行: Sprint O1+O4 (无依赖)

---

## 五、为什么我们不会复制 OpenHuman

1. **我们的优势在治理层，不在连接器数量上** — 118 个连接器不等于更好的系统。但 3-5 个关键连接器 + 完整的安全治理 = 更好的系统。

2. **我们是多 Agent 协作系统，不是单用户桌面助手** — L3 协作层让多个 Agent 协同工作，这是 OpenHuman 完全没有的。

3. **我们有自我认知层** — KOS self (L4) + metacog 让系统知道自己是谁，OpenHuman 没有这个概念。

4. **MCP 标准协议 vs 自定义内部协议** — 我们的系统天然可以接入任何 MCP 兼容项目，OpenHuman 做不到。

5. **运维体系是独一无二的** — 21 tools 的 hermes-ops 是 OpenHuman 完全没有的维度。

6. **最关键的理念差异**: 你的 2023 文章提出「AI 反向训练人类」——KOS self 的认知框架 + metacog 的理论基座已经在为这个目标打底了。OpenHuman 还在「帮用户记住和干活」的阶段。
