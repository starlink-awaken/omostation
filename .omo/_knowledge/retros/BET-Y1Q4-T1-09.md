---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-09 Closeout Retro — Portfolio dogfood canary
bet_id: BET-Y1Q4-T1-09
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-09 Closeout Retro

> **TL;DR**: Value-exempt canary fixture + `portfolio status`. 12 tests green.
> KRs marked proven on infrastructure evidence. Live control projection still
> unavailable (broker gap). No W1–W6. value=NOT_PROVEN.

## Deliverables
- `tests/test_bet_portfolio_canary.py` (12 passed)
- `bin/plan/bet-ledger.py` `portfolio status`
- `docs/reports/2026-09-03-w0-portfolio-v2-dogfood-canary.md`
- KR-TRUST-CHAIN-COVERAGE + KR-HOLDABILITY-ORPHAN-BETS → proven

## Q1
Appetite 3 days; same-day after T8-05 merge.

## Q2
- positive chain + digest stability: PASS (fixture)
- negative matrix typed fail: PASS
- parent close blocked on incomplete child: PASS
- live portfolio status met after KR proven + this bet done: PASS at closeout
- Cockpit/CLI control digest: both unavailable (documented; broker still missing)

## Q3
1. Live KRs were still `unmeasured` after all implementation children — milestones stayed UNMET until canary wrote KR evidence.
2. `portfolio status` subcommand was missing from verify contract — added rather than inventing a parallel CLI.
3. Control projection broker gap from T1-08 remains; canary must not invent Ledger fallback.

## Q4
+1 test file, +`portfolio status` handler; report+retro. GaC/ADR 0. Script baseline unchanged.

## Q5
T1-03 parent closeout: release human_gate with principal Wave auth; require all four W0 milestones derived met and no W1–W6. Do not treat unavailable control JSON as personal-value proof.
