---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# omostation 全景蓝图：架构·路线图·里程碑

> 日期: 2026-05-30 | 版本: v1.2 | 状态: 历史主蓝图 / reference
> 综合: architecture-final-vision · evolution-roadmap · beyond-phase4 · comprehensive-audit · tech-intelligence · phase1-4 task-specs · post-phase1 governance
> 本文档保留当时的全景规划假设、阶段拆分、数量级预估与路线图表达，属于历史设计输入，不是当前运行时 Phase、项目清单、能力计数或健康分 SSOT。
> 当前事实与执行许可以 `/.omo/goals/current.yaml`、`/.omo/state/system.yaml`、`/.omo/tasks/active/`、`/.omo/PROJECTS.yaml` 为准；端口、依赖与入口收敛以 `AGENTS.md`、`docs/PANORAMA.md`、`protocols/port-registry.yaml` 为准。

---

## 0. 当前执行基线

| 项 | 当前口径 |
|----|----------|
| Phase 1 | 工程交付基本完成，运行时证据待统一归档 |
| Phase 2 | full_execution，敏感能力继续走 gate/approval |
| 任务 SSOT | `.omo/tasks/active/*.yaml` |
| 当前目标 | `.omo/goals/current.yaml` |
| 规划注册表 | `.omo/plans/README.md` |
| 交付/测试标准 | `.omo/standards/planning-blueprint-delivery-test-standard.md` |

Phase 2 不再按 47 项任务全量启动，而是先完成治理收敛、KOS baseline、Safe Mesh，再开放 SSOT 7 域、真实知识闭环和连接器扩展。

## I. 全景架构图

```
                           ┌─────────────────────────┐
                           │    P0 — 用户入口层        │
                           │  wksp CLI · Agora Dashboard│
                           │  IDE 插件 · Hermes Agent  │
                           └───────────┬─────────────┘
                                       │
                           ┌───────────▼─────────────┐
                           │   I0 — Agora Service Mesh │
                           │  MCP 统一协议 · wksp:// URI│
                           │  100+ tools · 熔断·降级·路由│
                           └─┬───────┬───────┬───────┘
                             │       │       │
              ┌──────────────┘       │       └──────────────┐
              ▼                      ▼                      ▼
   ┌──────────────────┐ ┌──────────────────────────┐ ┌──────────────┐
   │   SharedBrain    │ │     kairon 知识操作栈       │ │  agentmesh   │
   │   合规控制面      │ │                          │ │  Agent运行时  │
   │                  │ │ ┌────────────────────┐   │ │              │
   │ EU经济 · 数字免疫│ │ │ L1 契约 (5包)       │   │ │ MCP网关      │
   │ A1身份 · 自愈    │ │ │ core-models        │   │ │ LLM路由      │
   │ 语音处理         │ │ │ eidos              │   │ │ 工具注册     │
   │ 14 活跃器官      │ │ │ family-models      │   │ │ 任务编排     │
   └──────────────────┘ │ │ work-models        │   │ └──────────────┘
                        │ │ media-models       │   │
                        │ └────────────────────┘   │ ┌──────────────┐
                        │ ┌────────────────────┐   │ │   gbrain     │
                        │ │ L2 能力 (10包)      │   │ │   知识脑     │
                        │ │ kronos · minerva    │   │ │              │
                        │ │ sophia · ontoderive │   │ │ memU后端     │
                        │ │ ssot · codeanalyze  │   │ │ Postgres     │
                        │ │ eu-pricing          │   │ │ 74 tools     │
                        │ │ token-juicer 🆕     │   │ └──────────────┘
                        │ │ memory-tree 🆕      │   │
                        │ │ bf-search 🆕        │   │ ┌──────────────┐
                        │ └────────────────────┘   │ │     ops      │
                        │ ┌────────────────────┐   │ │   运维中心    │
                        │ │ L3 协作 (8包)       │   │ │              │
                        │ │ forge · kos · iris  │   │ │ 32 tools     │
                        │ │ cross-domain        │   │ │ 7 SQLite表   │
                        │ │ kems-runtime        │   │ │ 关联引擎     │
                        │ │ trust-layer 🆕      │   │ └──────────────┘
                        │ │ skill-router 🆕     │   │
                        │ └────────────────────┘   │   基础设施服务
                        │ ┌────────────────────┐   │ ┌──────────────┐
                        │ │ L4 元层 (8包)       │   │ │ LiteLLM      │
                        │ │ agent-runtime       │   │ │ one-api      │
                        │ │ metaos · ecos       │   │ │ memU(Rust)   │
                        │ │ cron-service · wksp │   │ │ wx-cli       │
                        │ │ family-os 🆕        │   │ │ MinerU       │
                        │ │ kos-health 🆕       │   │ │ Firecrawl    │
                        │ │ device-orchestrator │   │ │ EdgeOne      │
                        │ └────────────────────┘   │ └──────────────┘
                        └──────────────────────────┘

                 5 项目 · ~30 kairon 包 · 100+ MCP tools
```

---

## II. 全局路线图

```
2026 Q2         Q3         Q4         2027 Q1       Q2         Q3         Q4+
  │              │           │            │           │           │           │
  ├─ Phase 1 ────┤           │            │           │           │           │
  │  基础设施     │           │            │           │           │           │
  │  (6周)        │           │            │           │           │           │
  │              ├─ Phase 2 ──┤            │           │           │           │
  │              │  知识深化  │            │           │           │           │
  │              │  (8周)     │            │           │           │           │
  │              │           ├─ Phase 3 ───┤           │           │           │
  │              │           │  辅助自主   │           │           │           │
  │              │           │  (12周)     │           │           │           │
  │              │           │            ├─ 验证期 ──┤           │           │
  │              │           │            │ (3-6月)    │           │           │
  │              │           │            │           ├─ Phase 4 ──┤           │
  │              │           │            │           │  高自主    │           │
  │              │           │            │           │  (持续)    │           │
  │              │           │            │           │           ├─ Phase ∞  │
  │              │           │            │           │           │  持续进化  │
  │              │           │            │           │           │  (永久)    │
```

### 各阶段概览

| Phase | 时间 | 时长 | Sprint | 任务 | 系统健康 |
|-------|------|:---:|:-----:|:---:|:--------:|
| **1**  基础设施 | Q2-Q3 2026 | 6周 | 3 | 24 | 66→75 |
| **2**  知识深化 | Q3-Q4 2026 | 8-10周 | M2.0-M2.5 | 47候选 / 6 gate | 75→82 |
| **3**  辅助自主 | Q4 2026-Q1 2027 | 12周 | 4 | 35 | 82→88 |
| —    验证期 | Q1-Q2 2027 | 3-6月 | — | 6 gate | 验证 |
| **4**  高自主   | Q2 2027+ | 持续 | — | 15 | 88→91 |
| **∞**  持续进化 | Q2 2028+ | 永久 | 季度 | — | 91→95 |

---

## III. 里程碑时间线

```
2026 ──────────────────────────────────────────────────────────── 2028+

Q2 2026                Q3 2026               Q4 2026            Q1 2027
│                      │                     │                  │
├ M1.1: P1收尾         ├ M2.0: 治理收敛       ├ M2.4: 真实知识闭环├ M3.1: KOS self就绪
│   SB×kairon整合完成  │ M2.1: KOS baseline   │ M2.5: 扩展评审    │   辅助自主率>50%
│   Code complete      │ M2.2: Safe Mesh      ├ M3.1: 跨域研究    ├ M3.2: 自愈全系统
│                      │ M2.3: SSOT 7域最小注册│                 │
│                      │                     │   家庭OS就绪      │   wksp://100%覆盖

Q2 2027               Q3 2027              Q4 2027             Q2 2028+
│                     │                    │                    │
├ M4.1: 辅助自主>50%  ├ M4.2: >70%        ├ M4.3: >80%        ├ 开源核心
│   系统可分发        │   联邦学习启动     │   健康≥91          │ Phase∞启动
│   健康≥88           │   社区Skill/Tool   │   3+用户           │ 联邦安全模型就绪
```

---

## IV. 能力增长矩阵

### kairon 包增长

```
Phase 1: 17 → 19 (+2: sharedbrain-bridge, eu-pricing)           ■■■■■■■■■■  ▢▢▢▢▢▢▢▢▢▢
Phase 2: 19 → 24 (+5: family-models, work-models, media-models,  ■■■■■■■■■■■■■■  ▢▢▢▢▢
                      token-juicer, trust-layer)
Phase 3: 24 → 28 (+4: cross-domain, memory-tree, skill-router,   ■■■■■■■■■■■■■■■■■■  ▢▢
                      device-orchestrator)
Phase 4: 28 → 30 (+2: bf-search, kems-runtime)                   ■■■■■■■■■■■■■■■■■■■■
```

### MCP 工具增长

```
当前:   33+ 工具 (8 opencode + 15 claude + ~12 kairon internal)     ████
Phase 1: 50+  工具 (+sharedbrain 20, +sharedbrain-bridge 5)        ██████
Phase 2: 80+  工具 (+model-garden, +obsidian, +apple, etc.)        ███████████
Phase 3: 100+ 工具 (+family, +device, +wechat, etc.)               ███████████████
Phase 4: 130+ 工具 (+template, +smb, +media, etc.)                 ██████████████████
Phase∞: 150+ 工具 (KOS self generated)                             ████████████████████
```

---

## V. Phase 任务规格书索引

| Phase | 文件 | 版本 | Sprint | 任务 | Agent 命令模板 |
|-------|------|:---:|:-----:|:---:|:-------------:|
| 1 | `phase1-task-specs.md` | v1.0 | 3 | 24 | reference |
| 2 | `phase2-task-specs-v2.md` | **v2.1** | M2.0-M2.5 | **47候选 / 6 gate** | execution-gated |
| 3 | `phase3-task-specs-v2.md` | **v2.1** | 4 | **35** | future-gated |
| 4 | `phase4-task-specs-v2.md` | **v2.1** | ∞ | **15** | future-gated |

---

## VI. 支撑文档索引

| 文档 | 用途 |
|------|------|
| `architecture-final-vision.md` | 终极架构（Workspace×SharedWork 全景融合） |
| `evolution-roadmap-4phases.md` v1.1 | 4 阶段路线图（红队修订版） |
| `comprehensive-architecture-audit.md` | SSOT 7 域拆解 + 架构缺口分析 |
| `tech-intelligence-2026q2.md` | 技术情报（50+ repos + 100+ 文章） |
| `beyond-phase4-vision.md` v1.1 | Phase ∞ 远景（红队修订版） |
| `beyond-phase4-review.md` | Phase ∞ 红队·战略·安全审查 |
| `redteam-revision-patch.md` | 全 Phase 红队修订补丁 |
| `sharedbrain-kairon-integration.md` v2.0 | SharedBrain 融合方案 |
| `phase1-sprint-plan.md` | Phase 1 Sprint 拆解 |
| `post-phase1-governance-and-phase2-entry.md` | Phase 1 关闭 + Phase 2 入场门禁 |
| `planning-blueprint-delivery-test-standard.md` | 规划、交付、测试统一标准 |
| `llm-convergence-requirements.md` | LiteLLM / LLM 路由统一收敛需求，纳入后续规划输入 |
| `llm-convergence-planning-packet.md` | dual_track 规划包：P2 尾波前置 + P3 主收敛包 |
| `phase2-phase3-task-manifest.md` | 当前 P2 尾波 / P3 future-gated 任务清单 |
| `` (本文件) | **全景主蓝图** |

---

## VII. 系统健康评分轨迹

```
 100 ┤                                              ╭────── Phase∞: 91→95
     │                                        ╭─────╯
  90 ┤                                  ╭─────╯ Phase4: 88→91
     │                            ╭─────╯
  80 ┤                      ╭─────╯ Phase3: 82→88
     │                ╭─────╯
  70 ┤          ╭─────╯ Phase2: 75→82
     │    ╭─────╯
  60 ┤────╯ Phase1: 66→75
     │
     └─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────
         Q2'26  Q3'26  Q4'26  Q1'27  Q2'27  Q3'27  Q4'27
```

---

## VIII. SSOT 7 域模型

```
omostation Knowledge Domains
├── 🧠 Knowledge  (Obsidian vaults, AI papers, KEMS methodology)
├── 💼 Work       (卫健委, 国转中心, legal, templates)
├── 👨‍👩‍👧‍👦 Family     (members, health, education, assets)
├── 🤖 AI         (462GB models, agents, tools, skills, pipelines)
├── ⚙️ System     (4+1+3+I architecture, .omo governance, ops)
├── 📁 Data       (iCloud, SharedDisk, Desktop, sync status)
└── 🎬 Media      (photos, videos, music, albums)
```

---

> **架构法则**: 10 条不可变法则（I0 隔离、MCP 强制、Python→kairon、TS→agentmesh/gbrain、SB 不做知识处理、kairon 不做运行时控制、core-models 唯一权威、器官可委托不可删除、吸收而非复制、每 Phase 安全扫描）

> **下次复审**: M2.2 Safe Mesh 验收后 | **主蓝图版本**: v1.1
