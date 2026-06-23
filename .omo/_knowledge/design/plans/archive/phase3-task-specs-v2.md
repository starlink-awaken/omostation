---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 3 任务规格书 v2.1（future-gated）

> 日期: 2026-05-30 | 版本: v2.1 | 依据: comprehensive-architecture-audit.md + post-phase1 governance
> 前序: Phase 2 full execution 必须验收通过；Safe Mesh、SSOT 7 域、真实知识闭环必须完成
> 变更: v1→v2 — 新增 M2/M3/M5/M6 + 2 Tech-Intel (MemoryTree/SkillRouter)

---

## 变更摘要

> **执行限制**: 本文件是 future-gated 规格书，不是当前执行源。KOS self、跨域研究、Family OS、WeChat、设备协同都依赖 Phase 2 M2.2 Safe Mesh 与 M2.4 真实知识闭环，不得提前进入 `.omo/tasks/active/`。

> **交叉规划输入**: `llm-convergence-planning-packet.md` 已将 LiteLLM / LLM 路由统一收敛拆成 `dual_track` 包；其中 P2 尾波前置项完成前，不应把主收敛包直接并入 Phase 3 execution。

Phase 3 v1.0 (3 Sprint, 25 任务) → Phase 3 v2.0 (4 Sprint, 35 任务)

| 来源 | 新增任务数 | 说明 |
|------|:--------:|------|
| M3 跨域研究引擎 | 2 | minerva 扩展到 7 域 |
| M2 家庭 OS 调度 | 2 | metaos 家庭运行时 |
| M5 WeChat 连接器 | 2 | iris 微信接入 |
| M6 设备协同 | 2 | mbp-m5 + y7000p 双机 |
| T4 Memory Tree | 1 | L2 记忆增强 (tech-intel) |
| T5 Skill Router | 1 | KOS self 技能路由 (tech-intel) |
| — 保留 v1.0 全部 | 25 | KOS self + 自愈 + wksp:// + 管线 |

---

## Phase 3 v2.0 全景 Sprint 视图

```
   Sprint 1 (3周)                Sprint 2 (3周)              Sprint 3 (3周)            Sprint 4 (2-3周)
 KOS self + 跨域研究         自愈 + 设备协同 + 家庭OS     wksp:// + 管线 + WeChat     集成验证 + 验收
┌──────────────────────────┐┌──────────────────────────┐┌──────────────────────────┐┌──────────────────────┐
│W1: KOS self辅助进化(v1)  ││W4: 器官自愈全系统化(v1) ││W7: wksp:// URI(v1)     ││W10: 全系统集成        │
│W1: 跨域研究引擎 🆕       ││W5: 设备协同 🆕          ││W8: 管线v2(v1)          ││W10: 跨域端到端测试    │
│W2: 家庭OS调度器 🆕       ││W5: 自愈学习+仪表盘(v1) ││W8: WeChat连接器 🆕      ││W11: 性能基线          │
│W3: 辅助发现+Skill路由🆕 ││W6: 家庭OS调度+事件 🆕   ││W9: 自动触发+72h(v1)    ││W11: 架构合规          │
│W3: Memory Tree 🆕       ││W6: 设备协同部署 🆕      ││W9: 管线编排器(v1)      ││W12: 文档+Phase3验收   │
└──────────────────────────┘└──────────────────────────┘└──────────────────────────┘└──────────────────────┘
```

---

## Agent 执行命令模板 — 新增任务

### M3: 跨域研究引擎

```bash
task(category="deep", description="M3: Cross-domain research engine", prompt='''
Create a cross-domain research engine in minerva that can research across all 7 SSOT domains.

Read: /Users/xiamingxing/Workspace/.omo/plans/comprehensive-architecture-audit.md (Section 2)

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/minerva/src/minerva/research/cross_domain.py

Requirements:
1. Cross-Domain Query Decomposition:
   - Input: "What impacts does government policy X have on family health?"
   - Decompose into sub-queries:
     - Work domain: find policy X details
     - Knowledge domain: find academic research on policy impacts
     - Family domain: find family health data
   - Fan out to each domain in parallel

2. Result Fusion:
   - Collect results from all domains
   - Cross-reference: connect entities across domains
   - Rank by relevance and cross-domain linkage strength
   - Generate unified research synthesis

3. Domain Priority:
   - Work → Knowledge → Family → AI → System → Data → Media
   - Each domain's results weighted by relevance

4. Expose as MCP tool: "minerva_cross_domain_research"
   - research <query> [domains: list] → synthesizes results across domains

5. Test: query "AI regulation impact on government projects and family technology use"
   → verify results come from ≥3 domains
6. Report: "Cross-domain research: <N> sub-queries across <M> domains, synthesis generated"
''')
```

### M2: 家庭 OS 调度器

```bash
task(category="unspecified-high", description="M2a: Family OS scheduler", prompt='''
Create a family OS runtime scheduler.

Read SSOT family domain: /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/family.yaml

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/metaos/src/metaos/family_os_scheduler.py

Requirements:
1. Daily Brief (早晨呈现):
   - Today's calendar events (from apple_connector)
   - Today's family reminders (birthdays, anniversaries, appointments)
   - Health check-ins (medication reminders, scheduled checkups)
   - Education update (homework deadlines, school events)

2. Event Triggers:
   - Member birthday approaching (7 days → 3 days → 1 day → today)
   - Health appointment upcoming
   - Document deadline approaching
   - Family member milestone

3. Integration:
   - apple_connector: calendar + reminders
   - family domain: member profiles, health records
   - KOS: any knowledge domain research relevant to family

4. Expose as MCP tool: "metaos_family_daily_brief"
   - brief: generate today's family brief
   - remind <event>: schedule a reminder
   - member <name>: show member profile with upcoming events

5. Test: generate daily brief → verify: calendar events appear, upcoming birthdays flagged, health reminders listed
6. Report: "Family OS scheduler: daily brief with <N> events, <M> reminders"
''')
```

### M5: WeChat 连接器

```bash
task(category="unspecified-high", description="M5: WeChat connector", prompt='''
Create an iris connector for WeChat integration.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/iris/src/iris/connectors/wechat_connector.py

Requirements:
1. WeChat Message Access (if wx-cli available):
   - Read recent messages from specified contacts
   - Extract: sender, content, timestamp, media attachments
   - Convert to work/personal domain entities

2. WeChat File Access:
   - Scan WeChat file directory (typically ~/Library/Containers/com.tencent.xinWeChat/)
   - Index: documents, images, videos shared via WeChat

3. WeChat Contact Sync:
   - Export contacts → family/work domain Member entities
   - Map to existing identity_bridge if applicable

4. Privacy Controls:
   - Do NOT auto-read without human opt-in per contact
   - Flag: "WeChat connector requesting access to <N> contacts — approve?"
   - Only index approved contacts

5. Expose as MCP tool: "iris_wechat"
   - index_files: scan WeChat file directory → index to KOS
   - list_contacts: show available contacts
   - approve <contact>: grant access to a contact's messages

6. If wx-cli is not available, create the connector with a stub interface:
   - Return: "WeChat access requires wx-cli at /path/to/wx-cli"
   - Document the dependency

7. Test: list contacts → approve 1 test contact → read messages
8. Report: "WeChat connector: <N> contacts available, <M> files indexed"
''')
```

### M6: 设备协同

```bash
task(category="unspecified-high", description="M6: Device orchestrator", prompt='''
Create a device orchestrator for mbp-m5 + y7000p dual-machine coordination.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/metaos/src/metaos/device_orchestrator.py

Requirements:
1. Device Inventory:
   - mbp-m5 (local): macOS, primary development machine
   - y7000p (remote): SSH-accessible Linux/Windows, compute node
   - SharedDisk (SMB): NAS storage accessible from both
   - Model volume: 462GB models on external SSD

2. Capability Mapping:
   - mbp-m5: Python dev, Docker, Obsidian, primary interaction
   - y7000p: heavy compute (model training, batch processing), CUDA if available
   - SharedDisk: shared file storage, backup target, media library

3. Task Distribution:
   - Light tasks (<10min): run locally on mbp-m5
   - Heavy tasks (>10min): SSH to y7000p, run there
   - Model inference: check Model volume access on both devices
   - File operations: use SharedDisk for cross-device access

4. Health Monitoring:
   - Ping y7000p every 60s → unreachable → alert
   - Check SharedDisk mount → unmounted → alert
   - Disk space check on all devices

5. Expose as MCP tool: "metaos_device_orchestrator"
   - status: show all device statuses
   - dispatch <task> [device]: send task to specific device
   - recommend <task>: suggest best device for task

6. Test: check device statuses → dispatch a test task to y7000p via SSH → verify result
7. Report: "Device orchestrator: <N> devices monitored, dispatch test: PASS/FAIL"
''')
```

---

## Phase 3 v2.0 验收清单 (新增条目)

```
□ P3.新增 — 跨域研究
  □ Cross-domain research operational
  □ Query involving 3+ domains → synthesis generated correctly
  □ Domain priority ranking works

□ P3.新增 — 家庭 OS
  □ Daily brief generated with calendar + reminders + health
  □ Event triggers: birthday approaching → alert
  □ Integration with apple_connector + family domain

□ P3.新增 — WeChat 连接器
  □ WeChat connector operational
  □ Contact listing: available (privacy preserved)
  □ File indexing: WeChat files → KOS

□ P3.新增 — 设备协同
  □ Both devices monitored
  □ Task dispatch: test task on y7000p via SSH
  □ Health check: disk space + mount status

□ P3.保留 — v1.0 全部 (25 任务)
  □ KOS self: 辅助进化 (nuwa-skill, schema/tool discovery, prompt优化)
  □ 器官自愈: 全系统化 + 级联保护
  □ wksp:// URI: 100% 映射
  □ Pipeline v2: 辅助自主研究管线 + 72h 验证
  □ 集成 + 文档
```

---

## 🆕 技术情报驱动的新增任务

### T4: Memory Tree 分层记忆 (Sprint 2, gbrain/gbrain)

```bash
task(category="deep", description="T4: Memory Tree for gbrain", prompt='''
Create a hierarchical Memory Tree storage for gbrain. Inspired by OpenHuman's Memory Tree.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/gbrain/src/memory_tree.py

Requirements:
1. Hierarchical Summarization:
   - Raw memory (chat/query/result) → leaf-level
   - Hourly summary: 5-10 memories → 1 summary
   - Daily summary: 24 hourly → 1 daily
   - Weekly summary: 7 daily → 1 weekly
   - Monthly summary: 4 weekly → 1 monthly

2. Auto-Compression:
   - Older memories → higher-level summaries (lossy but semantic-preserving)
   - Recent memories → full detail retained
   - User can "pin" important memories to prevent compression

3. Query Routing:
   - Search query → find most relevant summary level
   - Detail drill-down: from monthly → weekly → daily → hourly → raw
   - Token-efficient: only load needed detail level

4. Integration with existing gbrain 74 tools:
   - New MCP tool: "gbrain_memory_tree"
     - summarize <level>: generate summaries
     - search <query>: tree-search with drill-down
     - pin <memory_id>: prevent compression
     - stats: show tree health (depth, compression ratio, token savings)

5. Memory Tree data: stored alongside existing gbrain Postgres

6. Test: ingest 100 memories → summarize → verify: drill-down works
7. Report: "Memory Tree: depth=<N>, compression ratio=<X>%, drill-down test: PASS"
''')
```

### T5: Skill Router 技能路由 (Sprint 1, KOS self/kos)

```bash
task(category="unspecified-high", description="T5: Skill Router for KOS self", prompt='''
Create an intelligent Skill routing mechanism for agentmesh agents. Inspired by zhengyanzhao1997/SkillRouter.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/kos/src/kos/skill_router.py

Requirements:
1. Skill Registry:
   - Index all registered Skills (from KOS self + awesome-agent-skills + custom)
   - Extract: skill name, description, tags, trigger conditions, required tools
   - Store as KOS entities in the AI domain

2. Skill Matching:
   - Input: agent task description + available tools
   - Match: find top-K skills relevant to the task
   - Rank: by relevance score (task description similarity × required tools overlap)

3. Skill Chaining:
   - If task requires multiple skills → recommend a skill chain
   - Chain: skill A output → skill B input → skill C final
   - Example: "Write a research paper on X" → nuwa-skill(thinking frame) → scientific-agent-skill(research) → content-creator(write)

4. Skill Feedback Loop:
   - If human rejects a skill recommendation → record reason
   - KOS self learns: which skills pair well, which don't
   - Improves future recommendations

5. Expose as MCP tool: "kos_skill_router"
   - match <task_description>: find top-K skills
   - chain <task_description>: recommend skill chain
   - register <skill_definition>: register a new skill

6. Test: input "research AI regulation impact" → verify: recommends scientific-agent-skills
7. Report: "Skill Router: <N> skills registered, match test: PASS"
''')
```

### Phase 3 v2.0 验收新增

```
□ P3.新增 — Memory Tree
  □ Hierarchical summaries generated (hourly/daily/weekly/monthly)
  □ Drill-down: from monthly summary → raw memory works
  □ Pin: important memories preserved
  □ Compression ratio > 60%

□ P3.新增 — Skill Router
  □ Skill registry populated
  □ Task→Skill matching: top-K relevant
  □ Skill chaining: 2+ step chains work
  □ Feedback loop: rejected skills tracked for learning
```
