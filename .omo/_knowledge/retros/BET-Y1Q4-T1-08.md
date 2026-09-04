---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-08 Closeout Retro — Portfolio projections
bet_id: BET-Y1Q4-T1-08
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-08 Closeout Retro

> **TL;DR**: One-way projection generator. Markdown applied; both `.omo` targets remain `unavailable` because `portfolio-status.json` lacks a registered broker (`PORTFOLIO_BROKER_OWNER_MISSING`). Direct `.omo` writes forbidden.

## Deliverables
- `bin/plan/portfolio_projection.py` + registry + `bet-ledger portfolio project-goals`
- `docs/plans/3Y-BET-PORTFOLIO.md`
- tests (8 passed)

## Q1
Appetite 3 days; delivery after principal Wave auth.

## Q2
- shared digest / byte-identical / drift / direct-I/O / missing ledger: PASS
- `.omo` broker apply: halted as designed (owner missing for portfolio-status)
- Markdown apply + `--check`: PASS

## Q3
1. Plan predicted broker halt — confirmed: goals has ingress brokers, portfolio-status does not.
2. Separate broker amendment still required before Goals/control JSON can be applied.

## Q4
+1 script (baseline 578→579); Markdown projection; GaC/ADR 0.

## Q5
Do not direct-write `.omo/goals/current.yaml` or `portfolio-status.json`. Next: T8-05 Cockpit read-only consumer can read Markdown + unavailable control envelope.
