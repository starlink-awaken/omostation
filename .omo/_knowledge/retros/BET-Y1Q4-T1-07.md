---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-07 Closeout Retro — legacy BET classification manifest
bet_id: BET-Y1Q4-T1-07
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-07 Closeout Retro

> **TL;DR**: Wave A2 read-only migration manifest. Every Ledger BET classified exactly once; `--apply` fail-closed; source digest bound; zero Ledger mutation from dry-run.

## Deliverables

- `bin/plan/portfolio_migration.py` — inventory/classify/render + CLI
- `tests/test_bet_portfolio_migration.py`
- `docs/generated/bet-portfolio-migration-manifest.yaml`
- `bin/_registry/scripts/governance/portfolio_migration.yaml`
- Spec `1.0.0 → 1.0.1` (`implementation_authorized: true`)
- Ledger: human_gate false; write_surfaces expanded; `meta.total_bets=293`

## Q1 实际耗时 vs appetite？

Appetite 2 days。本轮约 1–2h（前置 self-binding #3085 + 写面扩权）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| manifest 覆盖全部 BET 恰好一次并绑定 source digest | PASS（293 rows） |
| terminal/blocked 语义不变；non-terminal 唯一分类 | PASS（fixture + live dry-run） |
| dry-run 零 mutation；apply 无授权/批>8 fail-closed | PASS |

## Q3 打假

1. tip 在 #3086 后 `meta.total_bets=289` vs `len=293` — 本轮一并修复。
2. 初始 write_surfaces 缺 registry/ledger/baseline — 先经 T1-03 amendment 扩权再实现。
3. `--apply` 本 BET 永不授权；分类不是业务关停决定。

## Q4 净增减

- 新文件 +4：migration.py / test / manifest / registry yaml
- script_baseline 577→578
- GaC/ADR：0

## Q5 下一任

1. 不要对本模块开 `--apply`；apply 需独立批次 BET（≤8）。
2. T1-08 / T1-06 仍按 parent Wave 顺序；T1-06 gate 已 false。
3. manifest source_digest 随 Ledger 变；改 Ledger 后需重跑 dry-run 再生。
