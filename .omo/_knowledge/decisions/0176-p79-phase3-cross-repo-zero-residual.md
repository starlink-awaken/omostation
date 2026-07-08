---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-08
related:
  - STRAT-P79-strategic-roadmap.md
  - 0174-p79-phase1-foundry-v2-cron.md
  - 0172-p78-port-registry-convergence.md
  - 0164-p77-phase1-cross-repo-consistency.md
  - ../../../../../projects/ecos/port-registry.yaml
  - ../../../../../protocols/port-registry.yaml
  - ../../../../../projects/agora/etc/bos-services.yaml
supersedes: []
---

# ADR-0176: P79 Phase 3 — 跨仓零残留 (ecos 对齐 + 孤儿 URI 清理)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-08), P79 STRAT § 2 Phase 3 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **ecos port-registry 结构化** | ✅ | name/transport/status 对齐 protocols |
| **8765/9090 deprecated** | ✅ | ecos 标记 status: deprecated |
| **8766 forge-api 注册** | ✅ | 新增 Active 端口 |
| **BOS URI unregistered** | ✅ | 0 unregistered (已是最优) |
| **孤儿 URI 文档** | ✅ | 29 orphan URIs 确认正常 (prefix 模式) |
| **ADR-0176** | ✅ | 本 ADR |

## 1. 决策

### 1.1 WHY

P79 STRAT Phase 3: 跨仓残留清零. 两项工作:
1. ecos port-registry 与 protocols 结构对齐 (P78 已结构化 protocols, ecos 没跟上)
2. unregistered BOS URI 清零

### 1.2 ecos port-registry 对齐

ecos 从 `7422: agora-mcp-http` 平面格式改为结构化:
```yaml
7422:
  name: agora-mcp-http
  transport: http
  status: active
```
这样跨仓 detector 不再报 false positive "port conflicts".

### 1.3 BOS URI 状态

cross-repo detector: unregistered=0 ✅, orphan=29.
29 orphan URIs 全部是 bos-services.yaml 中的 prefix 模式 (如 `bos://capability/bus/data`) — 属于 SSOT 声明的路由前缀, 不需要代码引用. 非残留.

## 2. 沉淀原则 (沿用 P79-1..5)

本 phase 无新增原则.
