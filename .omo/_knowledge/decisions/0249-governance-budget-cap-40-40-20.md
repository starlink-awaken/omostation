---
id: ADR-0249
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-07-26
related:
  - 0247-strategic-pivot-collab-first-physical-deferred.md
supersedes: []
amends: []
type: ssot
---

# ADR-0249: 治理自省预算封顶 (40/40/20, 用户已同意)

## Context

P82 长程规划 §B 治理自省预算约束 (用户 2026-07-26 口头同意, 本 ADR 正式化).
防止"治理完美但没干活" — 治理自省占比封顶, 协作主轴保底.

## Decision

| 约束 | 值 |
|------|-----|
| 治理自省占比 | ≤ **40%** (三份治理方案 + 巡检 + 漂移门等全部计入) |
| 协作主轴占比 | ≥ **40%** (ADR-0247 协作优先, ADR-0236/0237 三条线深化) |
| 弹性 | 20% (止血 / 纵贯线 / 临时) |
| 同时在推治理 Phase | ≤ **2** (超出排队) |
| 启动下一治理 Phase 前置 | 须有一轮协作主轴实质交付 (防治理连推) |
| 兜底熔断 | X3 连续两月 < 阈值 → **强制暂停全部治理自省** |

## Enforcement

- BRIEF 增"治理预算"指标 (generate-brief, 与决策积压并列) — 让占比可见
- 变更约束须人类拍板, agent 不得以"治理更重要"绕过
- 治理占比破 40% 须送卡 (P82 红线)

## Status

**ACCEPTED** (2026-07-26, 用户口头同意正式化).
