---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-08
related:
  - STRAT-P79-strategic-roadmap.md
  - 0174-p79-phase1-foundry-v2-cron.md
supersedes: []
---

# ADR-0175: P79 Phase 2 — Health 100 (bare ports 分类 + env var 迁移)

> P79 STRAT § 2 Phase 2 收口. 5 bare ports → env var, 10 ports EXEMPT, health 95→100.

## TL;DR

| 交付 | 状态 |
|------|:----:|
| 7430/7431/8080 env var 迁移 (cockpit/agora) | ✅ |
| 32 bare ports 分类: 5 FIX + 5 EXEMPT | ✅ |
| health.yaml: 95→100 | ✅ |
| cc-switch 环境 gap 文档化 | ✅ |
