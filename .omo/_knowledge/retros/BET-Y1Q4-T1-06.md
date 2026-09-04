---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-06 Closeout Retro — Milestone/Vision derived gates
bet_id: BET-Y1Q4-T1-06
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-06 Closeout Retro

> **TL;DR**: Read-only Milestone/Vision predicates on chain_bind. False-close / value-proxy / incomplete-window typed failures; no Ledger mutation.

## Deliverables
- `evaluate_milestone` / `evaluate_vision` in `bin/plan/chain_bind.py`
- `chain-bind-check portfolio` CLI
- `tests/test_bet_portfolio_completion.py` (9 cases)
- Spec 1.0.1 authorized

## Q1
Appetite 2–3 days; this delivery ~half day after Wave A2.

## Q2
done_when covered by pytest + self-check + ledger lint.

## Q3
1. Existing `test_chain_bind` fixtures drifted (done BETs / completion matrix) — repaired for tip compatibility.
2. Predicates never write KR proven or BET status.

## Q4
+1 test file; chain_bind/chain-bind-check additive LOC; GaC/ADR 0.

## Q5
T1-08 projections next in Wave B; do not let agents write derived Milestone/Vision status.
