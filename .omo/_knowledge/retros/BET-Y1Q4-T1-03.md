---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-03 interim — ledger truth restore (not parent closeout)
bet_id: BET-Y1Q4-T1-03
status: active
lifecycle: history
owner: portfolio-v2-governance
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-03 interim retro (ledger restore only)

> **Not a parent closeout.** Status remains `candidate`. This records the
> 2026-09-04 truth-restore wave only.

## Q1 实际耗时 vs appetite？
Restore session ~1h. Parent appetite unchanged.

## Q2 done_when 是否全部通过？
Parent done_when **not** claimed. Only restored missing BET rows after #2993 wipe.

## Q3 打假
1. Specs/plans/waiver survived on tip; BET rows did not — declaration≠ledger.
2. Wipe vector: #2993 squash of stale ledger base onto first-parent main after #3004/#3007.
3. T1-04 remains ★ human_gate; Wave A1 validator (#3009) still needs registry amendment.

## Q4 净增减
+8 BET rows in `3y-bet-ledger.yaml`; +1 restore report. No code/ADR/scripts.

## Q5 下一任
1. Human-gate T1-04 → register `bin/_registry/scripts/governance/portfolio_contract.yaml`
2. Re-land closed PR #3009 compatibility validator
3. Separate claim for `meta.total_bets` repair then self-binding
