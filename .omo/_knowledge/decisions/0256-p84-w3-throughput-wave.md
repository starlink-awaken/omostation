---
id: ADR-0256
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-07-28
related:
  - .omo/plans/strat-p84-scenario-driven-longplan.md
  - 0252-metaos-d1d4-aaaa-phase12.md
type: ssot
---

# ADR-0256: P84 W3 产能轨波次 — 真实任务记账纪律

## Decision
1. 产能轨只计 `.omo/tasks/done/*.yaml` 真实完成 (PR/证据), **禁止** 为空冲 30 造卡.
2. 已合 PR 可 **回填** done 卡 (SSOT 对齐), 须挂 PR 号.
3. 本波: done 5→14; completion_rate 约 78%; 距 ≥30 还差 16 (诚实).
4. 同步: bos-registry CI 漂移修; admit observe 默认; recommend_mode CLI.

## Status
**ACCEPTED** 2026-07-28.
