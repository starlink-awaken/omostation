# Phase 4 任务规格书 + Agent 执行手册

> 日期: 2026-05-29 | 版本: v1.0 | 依据: evolution-roadmap-4phases.md v1.1
> 前序: Phase 3 必须验收通过
> 类型: 持续迭代 (Continuous)，非阶段式冲刺
> ⚠️ 核心原则: 所有自主决策保留人工审核。KOS 推荐 → 人类确认 → 生效。85%+ 操作有 AI 辅助但不脱离人类控制。

---

## Phase 4 概览

Phase 4 与其他阶段不同——它不是一个有限时间内的冲刺集合，而是一个**持续运行的目标态**。系统在日常操作中 > 80% 有 AI 辅助建议，但关键决策保留人工审核。

### 目标

| 目标 | Q2 2027 | Q3 2027 | Q4 2027 | 长期 |
|------|:------:|:------:|:------:|:----:|
| 辅助自主率 | > 50% | > 70% | > 80% | > 90% |
| 推荐准确率 | > 90% | > 93% | > 95% | > 98% |
| 自愈成功率 | > 90% | > 93% | > 95% | > 98% |
| 新能力发现速度 | 1/月 | 1/2周 | 1/周 | 2/周 |
| 系统健康评分 | ≥ 88 | ≥ 90 | ≥ 91 | ≥ 93 |

### 架构状态

```
Phase 4 运行态:
┌──────────────────────────────────────────────────────┐
│                                                    │
│  ██ 高自主运行 (High Autonomy + Human-in-the-Loop) ██ │
│                                                    │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│  │ KOS 辅助   │ │ 自愈系统  │ │ 分发系统   │       │
│  │ • 推荐Skill│ │ • 自动恢复 │ │ • 安装脚本 │       │
│  │ • 推荐Schema│ │ • 推荐修复 │ │ • 配置向导 │       │
│  │ • 推荐Tool │ │ • 自动回滚 │ │ • 文档生成 │       │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘       │
│        │              │              │              │
│    人类确认        人类确认        自动完成          │
│                                                    │
│  人类角色: 审核新能力 + 处理异常 + 设定战略目标       │
│                                                    │
└──────────────────────────────────────────────────────┘
```

---

## 📋 任务规格 (按目标域组织)

### P4.1 — 辅助自主度提升 (持续)

```bash
# P4.1a: 辅助自主度度量
task(category="writing", description="P4.1a: Autonomy metrics dashboard", prompt='''
Create a metrics dashboard in Agora tracking assisted autonomy levels.

1. Define metrics:
   - AAR (Assisted Autonomy Rate): % of operations with AI recommendation
   - EAR (Execution Acceptance Rate): % of AI recommendations accepted by human
   - MTR (Mean Time to Resolve): with vs without AI assistance
   - HCR (Human Confirmation Rate): % of decisions requiring human review

2. Data sources:
   - KOS self: skill/schema/tool proposals logged
   - Agora: MCP calls that go through HITL gates
   - agentmesh: agent execution logs with human confirmations

3. Add metrics to Agora Dashboard
4. Set up weekly metrics reports → .omo/metrics/autonomy/
5. Report: "Autonomy dashboard: metrics tracked, first baseline recorded"
''')

# P4.1b: 反馈循环优化
task(category="writing", description="P4.1b: Feedback loop for recommendations", prompt='''
Implement a feedback loop to improve AI recommendations based on human decisions.

1. Create kairon/packages/kos/src/kos/self/feedback_collector.py
   - Records: recommendation, human decision, time taken, eventual outcome
   - Identifies: which recommendations are most often accepted/rejected
2. Create kairon/packages/kos/src/kos/self/recommendation_improver.py
   - Learns from feedback to improve future recommendations
   - ⚠️ Human-in-the-loop: improvement strategies → human reviews quarterly
3. Implement A/B testing: new recommendation strategy vs old strategy
4. Report: "Feedback loop: N recommendations tracked, acceptance rate: X%"
''')
```

### P4.2 — 系统分发 (持续)

```bash
# P4.2a: 一键安装
task(category="quick", description="P4.2a: One-click install", prompt='''
Create a one-click installation script for the entire omostation system.

1. Create /Users/xiamingxing/Workspace/install.sh that:
   - Checks prerequisites: Python 3.12+, Bun, Docker, Git
   - Clones/clones all repos
   - Runs pip install/bun install for all packages
   - Initializes databases
   - Starts all services via docker compose
   - Runs smoke test to verify

2. Test: fresh clone + ./install.sh
3. Goal: 1 command, 0 manual steps, < 15 minutes
4. Report: "install.sh: <N> steps, fresh install test: PASS/FAIL, duration: <X>min"
''')

# P4.2b: 配置向导
task(category="quick", description="P4.2b: Configuration wizard", prompt='''
Create a configuration wizard for new users.

1. Create /Users/xiamingxing/Workspace/configure.sh (or Python script) that:
   - Asks for: LLM API keys, Docker registry, admin password, data directory
   - Generates .env files for all services
   - Validates configuration (LLM key works, Docker accessible, etc.)
   - Sets up RBAC roles for the initial admin

2. Test: run wizard with test values → verify .env files generated → verify services start
3. Report: "Configuration wizard: N config values collected, services started: PASS/FAIL"
''')

# P4.2c: 自文档化
task(category="writing", description="P4.2c: Self-documenting system", prompt='''
Create an auto-documentation system that generates docs from the running system.

1. Create script at scripts/generate_docs.sh that:
   - Reads Agora registry → generates API docs
   - Reads eidos schemas → generates data model docs
   - Reads .omo/ → generates architecture docs
   - Reads KOS index → generates knowledge map docs
   - Outputs to docs/ (static HTML or markdown site)

2. Set up cron to regenerate weekly
3. Test: run script → verify docs generated → verify accuracy
4. Report: "Auto-docs: N pages generated, <N> tools documented, <N> schemas documented"
''')
```

### P4.3 — 持续健康监控 (持续)

```bash
# P4.3a: 系统健康自动评分
task(category="quick", description="P4.3a: Automated health scoring", prompt='''
Automate the system health scoring (D1-D8 dimensions).

1. Create kairon/packages/ecos/health_scorer.py that:
   - D1 (Vision): check .omo/plans/ completeness
   - D2 (Coverage): count MCP tools, agent types, ingestion formats
   - D3 (Stories): check test coverage
   - D4 (Maturity): check service uptime, test pass rate
   - D5 (Architecture): run compliance checker
   - D6 (Entropy): code churn, TODO count, delegated count
   - D7 (Security): secrets scan, dependency audit
   - D8 (Tech Debt): delegated organs, deprecated APIs, skipped tests

2. Expose as MCP tool: "ecos_health_score"
3. Generate weekly health report → .omo/health/
4. Report: "Health scorer: D1-D8 computed, score: XX/100"
''')

# P4.3b: 异常检测 + 人工通知
task(category="quick", description="P4.3b: Anomaly detection + human notification", prompt='''
Implement proactive anomaly detection that notifies humans BEFORE attempting auto-heal.

1. Create kairon/packages/ecos/anomaly_detector.py
   - Monitors: service health, MCP latency, error rates, EU balance, disk/memory
   - Detects: deviations from baseline (Z-score > 3)
   - ⚠️ Human-in-the-loop for HIGH severity: notify → wait → human decides → act
   - Auto-act for LOW severity: restart, clear cache, etc.

2. Notification channels: console log + optionally email/webhook
3. Dashboard: anomaly timeline in Agora
4. Test: simulate high latency → verify detection + notification
5. Report: "Anomaly detector: N services monitored, detection test: PASS"
''')
```

### P4.4 — 能力边界扩展 (持续)

```bash
# P4.4a: SharedWork 持续融入
task(category="writing", description="P4.4a: SharedWork continuous integration", prompt='''
Set up a process for continuously evaluating and integrating SharedWork projects.

1. Create /Users/xiamingxing/SharedWork/CATALOG.md (or update existing)
   - Status for each project: integrated / candidate / reference / archived
   - Integration priority: P0 (critical) / P1 (valuable) / P2 (nice-to-have)
2. Monthly review process:
   - Scan SharedWork for new projects
   - Evaluate against architecture laws
   - Decide: integrate / reference / skip
3. Integration template (reusable checklist for each new project)
4. Report: "SharedWork catalog: N projects, <status distribution>"
''')

# P4.4b: 新协议 / 新框架 适配
task(category="writing", description="P4.4b: New protocol/framework adaptation", prompt='''
Establish a process for evaluating and adopting new AI protocols and frameworks.

1. Monitor list (to be maintained):
   - MCP protocol updates (Anthropic)
   - New agent frameworks (CrewAI, AutoGen, LangGraph, etc.)
   - New LLM APIs (new models, new capabilities)
   - New knowledge graph formats (RDF, OWL, etc.)

2. Quarterly evaluation: review list → decide which to adopt
3. Impact analysis template: cost vs benefit of adopting
4. Report: "Protocol watch: N items monitored, <pending decisions>"
''')
```

---

## 📋 Phase 4 验收检查清单

```
Phase 4 持续验收 — Prometheus 执行 (每季度)

□ P4.1 — 辅助自主度
  □ AAR (辅助自主率) ≥ target for current quarter
  □ Recommendation acceptance rate ≥ target
  □ Feedback loop: recommendations improving over time

□ P4.2 — 系统分发
  □ install.sh: fresh clone → all services up in < 15min
  □ configure.sh: wizard runs, config valid, services start
  □ Auto-docs: generated weekly, accurate, accessible

□ P4.3 — 健康监控
  □ Health score ≥ target for current phase (Q2: 88+, Q3: 90+, Q4: 91+)
  □ Anomaly detection: operational, LOW severity auto-healed
  □ Weekly health reports generated

□ P4.4 — 能力边界
  □ SharedWork catalog maintained (monthly update)
  □ New protocol evaluations: quarterly reviews documented
  □ At least 1 new SharedWork project integrated per quarter

□ P4.5 — 安全 + 质量
  □ Architecture 10 laws: continuous enforcement
  □ RBAC: no violations in audit logs
  □ EU economy: balanced (no runaway debt or infinite growth)
  □ Immune audit: false positive rate < 5%

□ P4.6 — 人类控制
  □ ALL high-severity autonomous decisions: human confirmation audit trail
  □ Emergency override: human can pause/stop any autonomous operation
  □ Monthly human review: system direction, priorities, guardrails updated
```

---

## Phase 4 与其他 Phase 的区别

| 维度 | Phase 1-3 | Phase 4 |
|------|-----------|---------|
| 时间模式 | 有限冲刺 | 持续运行 |
| 任务类型 | 构建新能力 | 优化已有能力 |
| 成功标准 | 任务 PASS/FAIL | 指标达标 |
| 人类角色 | 开发 + 审查 | 设定方向 + 异常处理 |
| 交付物 | 代码 + 文档 | 指标报告 + 改进 |
| 审查频率 | Phase 结束时 | 每季度 |
