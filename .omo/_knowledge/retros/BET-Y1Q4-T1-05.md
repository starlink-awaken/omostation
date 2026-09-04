---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-05 Closeout Retro — Objective/KR/BET coverage graph 与 critical path
bet_id: BET-Y1Q4-T1-05
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-05 Closeout Retro

> **TL;DR**: Pure Portfolio coverage graph + critical-path CLI. pytest 9/9; live `portfolio coverage` exit 0 (bootstrap); critical-path JSON byte-stable.

## Deliverables

- `bin/plan/portfolio_graph.py`
- `tests/test_bet_portfolio_graph.py` (9 passed)
- `bin/plan/bet-ledger.py` — `portfolio coverage|critical-path [--json]`
- `bin/_registry/scripts/governance/portfolio_graph.yaml`
- Spec `implementation_authorized: true`; `human_gate: false`
- `script_baseline` 576→577

## Q1 实际耗时 vs appetite？
Appetite 2 days. Implementation ~2h after T1-04 done/gate release.

## Q2 done_when
- dependency graph no missing ID / cycle on fixtures: PASS
- required KR / failed leaf / unbound fail-closed in fixtures: PASS
- critical-path JSON byte-stable with blocker/descendant/writer-lane: PASS
- live ledger coverage CLI exit 0 in bootstrap: PASS

## Q3 打假
1. T1-05 claim blocked until T1-04 `status=done` — completed first with delivery_accepted evidence.
2. Work packet initially omitted registry/baseline surfaces — expanded write_surfaces before implementation run.
3. Live ledger has no required KR entities yet (bootstrap_unenforced); CLI reports INFO gaps without failing unless `--strict`.

## Q4 净增减
+2 scripts (`portfolio_graph.py` + registry yaml), +1 test file, ~+40 LOC CLI wiring, baseline +1. No ADR.

## Q5 下一任
1. T1-06 Milestone/Vision completion predicates (`chain_bind` / `test_bet_portfolio_completion`) — still ★ until released.
2. Do not treat ready_bets length as progress.
3. New bin scripts need registry + baseline companions (same as T1-04).

## Addendum — status done (2026-09-04)

- `completion_evidence.overall_state=delivery_accepted`
- merged_reachable_commit: `git://origin/main@f25b5b97b133fe6965d18a7210d4ad0b638d77ac` (#3075)
- Downstream T1-06 human_gate released for sequential Wave A1
