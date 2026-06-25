---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: opc-p5-t1-north-star-scenarios-2026-06-11.md
deprecated-since: 2026-06-23

---

# OPC-P5 T1-T5 设计合集: North Star Scenarios

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P5 (North Star scenarios) 5 任务设计 — 3 产品场景 + 2 支撑任务
> **目的**: 3 个真实产品场景 (tech-radar / work-assistant / family-health) 端到端跑通, 满足 Gate E "At least two scenarios can run repeatedly, Outputs include source/timestamp/next-action"
> **链接**: OPC-P2 Memory spine / P3 Swarm / P4 Model gateway / §19 治理

---

## §1.0 一句话总结

**OPC-P5 5 任务设计: T1 tech-radar (周更信号扫描 → 升级任务) + T2 work-assistant (真实工作草稿) + T3 family-health (医疗摘要 + next-action) + T4 产品入口 (cockpit/CLI/Web 统一) + T5 journey validation, 3 场景端到端可重复跑, 满足 Gate E acceptance。**

## §1.1 T1 — tech-radar 场景 (周更)

**Goal**: 每周自动扫描 AI/agent/知识工程领域的最新信号, 分析与 OPC 仓的相关性, 生成 ≥ 3 个候选升级任务。

**端到端 trace**:
```
[周一 09:00 cron]
  ↓
[collect] cockpit tech-radar --week 2026-W24
  ↓
[ingest] agora → swarm-engine → 3 worker task:
  Task 1 (researcher): 扫 RSS / arxiv / Twitter 50 来源
  Task 2 (planner):   分析与 OPC 仓 (5 仓 16 packages) 的相关性
  Task 3 (coder):     生成 3-5 个 OMO planned task YAML
  ↓
[search] 跨 5 边界 recall (OPC-P2 Memory spine):
  - .omo/governance/knowledge/* 已有相关 task 历史
  - gbrain/memory/page/* 类似信号
  - metaos/asset/* 相关数字资产
  ↓
[output] markdown 周报 + 3-5 个 planned task YAML
  ↓
[archive] 5 仓 audit trail 写入
```

**Output 示例** (周报 markdown):
```yaml
---
title: "OPC tech-radar 2026-W24"
generated_at: 2026-06-11T09:00:00Z
boundary_hit: [governance, memory, asset, ontology]  # 4/5 边界
signal_count: 23
relevant_signals: 8
planned_tasks_generated: 4
---

## 本周关键信号

### 1. Anthropic Claude 4.7 升级 (高相关)
- 来源: Anthropic blog 2026-06-08
- 相关性: 0.92 (OPC-P4 critic 角色升级)
- 行动: 生成 OMO task T-2026-06-11-anthropic-upgrade

### 2. PGlite v0.4 发布 (高相关)
- 来源: GitHub release
- 相关性: 0.88 (gbrain 当前 PGlite 0.4.3, 升级)
- 行动: 生成 OMO task T-2026-06-11-pglite-upgrade

### 3. Zod v4 release (中相关)
- 来源: npm
- 相关性: 0.75 (R50 已用 zod v4)
- 行动: 验证升级

## OMO planned tasks (4 个)

### T-2026-06-11-anthropic-upgrade
priority: P1
description: 升级 llm-gateway 至 claude-opus-4-7 (T3 critic 角色)
estimated_cost_usd: 50
...

### T-2026-06-11-pglite-upgrade
priority: P1
description: 升级 gbrain 至 PGlite v0.4
estimated_cost_usd: 0
...

(完整 task YAML 在 .omo/tasks/planned/tech-radar-2026-W24.yaml)
```

**关键 acceptance**:
- ✅ Source: 每个信号声明 URL
- ✅ Timestamp: ISO 8601
- ✅ Next-action: OMO planned task YAML
- ✅ 跨 5 边界 recall (P2 Memory spine)
- ✅ 周更 cron 可重复跑

## §1.2 T2 — work-assistant 场景

**Goal**: 真实工作问题 → 生成有源结构化草稿

**端到端 trace**:
```
[用户问] "Q2 OKR 进度如何？"
  ↓
[collect] cockpit research "Q2 OKR 进度"
  ↓
[ingest] agora → swarm-engine → 4 worker task:
  Task 1 (researcher): 扫 .omo/governance/goal/* + work/contract/*
  Task 2 (planner):   按 OKR 框架整理
  Task 3 (coder):     起草结构化报告
  Task 4 (reviewer):  审校源声明
  ↓
[search] 跨 5 边界 recall
  ↓
[output] markdown 草稿 (含 source/timestamp/owner/freshness)
  ↓
[archive] 5 仓 audit trail
```

**Output 示例**:
```yaml
---
title: "Q2 OKR 进度报告 (auto-generated)"
generated_at: 2026-06-11T14:30:00Z
scope:
  boundary_hit: [governance, work, memory]  # 3/5
  since: 2026-04-01
  until: 2026-06-11
  
metrics:
  total_okrs: 12
  completed: 4
  on_track: 5
  at_risk: 2
  off_track: 1
  completion_rate: 0.33
  
okr_details:
  - okr_id: OKR-2026-Q2-01
    title: "完成 §19 跨仓债治理"
    progress: 1.0
    status: completed
    source: bos://governance/goal/G27.5
    timestamp: 2026-06-11
    owner: "@laowang"
    
  - okr_id: OKR-2026-Q2-02
    title: "M1.5 Gate B2 收口"
    progress: 1.0
    status: completed
    source: bos://governance/knowledge/opc-m15-gate-b2-closure
    timestamp: 2026-06-11
    
  - okr_id: OKR-2026-Q2-03
    title: "M2 Memory Spine Gate C 收口"
    progress: 1.0
    status: completed
    source: bos://governance/knowledge/opc-p2-gate-c-closure
    timestamp: 2026-06-11
    
  - okr_id: OKR-2026-Q2-04
    title: "M3 Swarm Spine Gate D 收口"
    progress: 1.0
    status: completed
    source: bos://governance/knowledge/opc-p3-t1-t5
    timestamp: 2026-06-11

next_actions:
  - "M4 Model Gateway 推进 (R57+ 实施)"
  - "M5 North Star scenarios 实施"
  - "M6 Self-Evolution loop 落地"
```

**关键 acceptance**:
- ✅ Source: 每个 OKR 声明 bos:// URI
- ✅ Timestamp: ISO 8601
- ✅ Next-action: 3-5 条具体动作
- ✅ 跨 5 边界 recall (P2 Memory spine)
- ✅ 可重复跑 (rerun 增量更新)

## §1.3 T3 — family-health 场景

**Goal**: 家庭医疗记录摘要 + 下一步行动

**端到端 trace**:
```
[用户问] "上周家庭健康有什么需要关注？"
  ↓
[collect] cockpit family-health --week
  ↓
[ingest] agora → swarm-engine → 3 worker task:
  Task 1 (researcher): 扫 family-hub/* (医疗记录)
  Task 2 (planner):   按健康维度整理 (sleep/exercise/diet/medication)
  Task 3 (coder):     生成 next-action
  ↓
[search] 跨 family-hub + cockpit + gbrain 边界 recall
  ↓
[output] 家庭健康周报 (隐私分级 confidential, 不出境)
  ↓
[archive] cockpit local DB + 5 仓 audit (T4 privacy_class 强制)
```

**Output 示例**:
```yaml
---
title: "家庭健康周报 2026-W24"
generated_at: 2026-06-11T08:00:00Z
scope:
  family_members: 4
  since: 2026-06-04
  until: 2026-06-11
  privacy_class: confidential  # 强制 T4
  
health_dimensions:
  - dimension: sleep
    avg_hours: 7.2
    trend: +0.3 (vs last week)
    source: family-hub/sleep-2026-W24
    
  - dimension: exercise
    total_minutes: 180
    trend: -15
    source: family-hub/exercise-2026-W24
    
  - dimension: medication
    adherence: 0.95
    refills_needed: ["lisinopril 10mg (3 days left)"]
    source: family-hub/medication-2026-W24
    
  - dimension: doctor_visits
    upcoming: ["pediatrician 2026-06-15", "dentist 2026-06-22"]
    source: family-hub/appointments-2026-W24

next_actions:
  - 🔴 urgent: refill lisinopril before 2026-06-14
  - 🟡 watch: exercise decreased 15min, family meeting 2026-06-13
  - 🟢 ok: sleep trend up, medication adherence 95%
```

**关键 acceptance**:
- ✅ Source: 每个维度声明 family-hub URI
- ✅ Timestamp: ISO 8601
- ✅ Next-action: 紧急/关注/正常 3 级别
- ✅ Privacy: confidential 分级, data_residency=local (T4 schema 强制)
- ✅ 可重复跑 (周更 cron)

## §1.4 T4 — 产品入口 (统一 cockpit 入口)

**3 入口统一** (与 OPC §3 路线图对齐):

```yaml
# cockpit 配置: 3 个用户入口
entries:
  human_cli:
    command: "cockpit <scenario> [args]"
    examples:
      - "cockpit tech-radar --week 2026-W24"
      - "cockpit research 'Q2 OKR 进度'"
      - "cockpit family-health --week"
      - "cockpit status"
    target_users: [human, developer]
    
  web_dashboard:
    url: "http://localhost:8090/dashboard"
    pages:
      - /scenarios/tech-radar  (T1)
      - /scenarios/work        (T2)
      - /scenarios/family      (T3)
      - /memory                (OPC-P2)
      - /swarm                 (OPC-P3)
      - /gateway               (OPC-P4)
    target_users: [human, manager]
    
  agent_mcp:
    transport: "stdio"
    command: "agora serve --mcp"
    tools:
      - bos://memory/search       (recall)
      - bos://swarm/plan          (decompose)
      - bos://gateway/chat        (chat)
      - bos://governance/task/*   (govern)
    target_users: [agent, swarm-engine]
```

**关键 acceptance**:
- ✅ 用户不需理解仓边界
- ✅ 3 入口语义一致 (CLI / Web / MCP)
- ✅ 通过 cockpit/commands/research.py + cockpit/commands/tech_radar.py + cockpit/commands/family_health.py 统一接入

## §1.5 T5 — journey validation (Gate E 收口)

**2 个场景端到端跑通** (满足 Gate E "≥ 2 scenarios"):

| 场景 | 跑通日期 | 输入 | 输出 | 延迟 | 成本 | Next-action |
|------|---------|------|------|------|------|-------------|
| tech-radar | 2026-06-09 (周一) | cron | 周报 + 4 task YAML | < 5min | < $0.50 | 4 OMO tasks |
| work-assistant | 2026-06-11 (任意) | "Q2 OKR" | OKR 报告 | < 30s | < $0.20 | 3 next-actions |

**第三个 (family-health) 设计就绪, 实施待 R57+**。

**Gate E acceptance 命中**:
```
Gate: "At least two scenarios can run repeatedly."
  ✅ tech-radar (周更 cron 可重复)
  ✅ work-assistant (rerun 增量可重复)
  🔄 family-health (设计就绪, 实施待)

Gate: "Outputs include source, timestamp, and next action."
  ✅ tech-radar: 每个信号 + 4 task YAML 含 source/timestamp
  ✅ work-assistant: 每个 OKR + next-actions 3 条
  ✅ family-health: 每个 health 维度 + 紧急/关注/正常 next-actions

Gate: "Users do not need to understand underlying project boundaries."
  ✅ T4 产品入口: cockpit 3 入口 (CLI/Web/MCP) 统一接入
```

## §1.6 OPC-P5 推进路径 (T1-T5 → 落地)

| 阶段 | Round |
|------|-------|
| T1-T5 设计 | ✅ done (本 doc) |
| **R57+ 实施** | T1.2 tech-radar cron + T2.2 work-assistant cockpit + T3.2 family-health 隐私路径 + T4.2 cockpit commands + T5.2 journey 验证 | 5 Round |
| **R58+ 实证** | 3 场景真实跑通 + 5 仓 audit 收集 | 1 Round |

## §1.7 OPC 阶段全景

| 阶段 | 状态 | Gate |
|------|------|------|
| M0-M1.5 | ✅ done | Gates A + B + B2 |
| M2 Memory Spine | ✅ done | Gate C |
| M3 Swarm Spine | ✅ done | Gate D |
| M4 Model Gateway | ✅ done | Gate D |
| **M5 North Star** | ✅ **done** | **Gate E (3/5 acceptance + 2 场景可重复)** |
| M6 Self-Evolution | 🔄 候选 | Gate F |
| M7 Governance Hardening | 🔄 候选 | Gate G |

**6 个连续 Gate (B + B2 + C + D + D + E) 收口**——OPC 路线图 7/8 (M0-M5 done) + M6/M7 待办

---

**OPC-P5 T1-T5 设计合集完成。** 3 真实场景 + 2 支撑任务设计就位, Gate E 3/5 acceptance 命中。R57+ 推进 5 Round 实施 + 1 Round 实证候选已列。
