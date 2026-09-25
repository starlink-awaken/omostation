---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
id: ADR-0175
related: 
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
