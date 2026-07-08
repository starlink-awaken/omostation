---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-08
related:
  - STRAT-P79-strategic-roadmap.md
  - 0176-p79-phase3-cross-repo-zero-residual.md
  - ../../../../../ARCHITECTURE.md
  - ../../../../../docs/project-registry.yaml
  - ../../../../../protocols/port-registry.yaml
supersedes: []
---

# ADR-0177: P79 Phase 4 — 文档刷新 (ARCHITECTURE.md + SSOT 契约)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-08), P79 STRAT § 2 Phase 4 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **Port Registry § 6** | ✅ | ARCHITECTURE.md 新增 port-registry architecture contract |
| **Section renumbering** | ✅ | 6→8, 7→9 (insert § 6) |
| **ADR-0177** | ✅ | 本 ADR |

## 1. 决策

### 1.1 WHY

P79 STRAT Phase 4: P77/P78 落地后 architecture docs 未反映变化.
ARCHITECTURE.md 没有 port-registry SSOT 契约, 新 reader 不知道端口治理规则.

### 1.2 WHAT

ARCHITECTURE.md § 6 新增:

```
## 6. Port Registry & Transport (P77/P78)

protocols/port-registry.yaml  — I0 SSOT (name, transport, status, env_var)
projects/ecos/port-registry.yaml  — L0 mirror (aligned to I0)

- Every service port must be registered with name/transport/status
- Ports via env var {SERVICE}_PORT, not literals
- Deprecated ports retain entry for history
- Foundry v2 validates on 6h cron cycle
```

## 2. 沉淀原则

沿用 P79-1..5.
