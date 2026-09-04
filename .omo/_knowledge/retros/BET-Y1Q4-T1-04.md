---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-04 Closeout Retro — Portfolio v2 schema 与兼容 validator
bet_id: BET-Y1Q4-T1-04
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-04 Closeout Retro

> **TL;DR**: Wave A1 落地 Portfolio v2 compatibility validator。`human_gate` 已由 principal 放行。pytest 5/5；`bet-ledger portfolio lint` exit 0（compat 模式对 `meta.total_bets` drift 出 WARN，不阻断）。full-Ledger strict + `meta.total_bets` 单字段修复仍按 done_when 要求走独立 claim。

## Deliverables

- `bin/plan/portfolio_contract.py` — additive Portfolio v2 compatibility validator
- `tests/test_bet_portfolio_contract.py` — focused fixtures（5 passed）
- `bin/_registry/scripts/governance/portfolio_contract.yaml` — GaC script-registry 授权
- `bin/plan/bet-ledger.py` — `portfolio lint [--strict]` CLI
- Spec bump `1.0.1 → 1.0.2`（registry write surface + authority note）
- Ledger：T1-04 `human_gate: false`；write_surfaces 增补 registry yaml；binding digest→1.0.2

## Q1 实际耗时 vs appetite？

Appetite 3 days。本轮实现+registry+verify ~2h（前置 attempt 产物可复用：validator 草稿、registry amendment）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| full v1 Ledger 在 v2 parser 下可读、既有 BET 语义等价 | PASS（compat lint OK） |
| valid v2 fixture + typed fail | PASS（pytest 5/5） |
| compat mode 对 meta.total_bets drift 出 typed warning、不阻断 v1 | PASS（`WARN META_TOTAL_BETS_DRIFT: declared=149 actual=289`） |
| focused fixtures strict meta.total_bets==len(bets) | PASS（fixture 覆盖） |
| **独立 claim** 修复 meta.total_bets → len(bets) | **DEFERRED**（validator 合并后下一 claim） |
| 单字段修复不改 BET object/status/binding/... | DEFERRED（随上条） |
| 修复后 full Ledger strict 全绿 | DEFERRED（随上条） |
| validator 无 import-time / filesystem write side effect | PASS |

Verify 命令（台账登记）：

```
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml --with pytest python -m pytest tests/test_bet_portfolio_contract.py -q
# 5 passed

PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python bin/plan/bet-ledger.py portfolio lint
# OK -- Portfolio v2 compatibility contract (exit 0)
```

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **#2993 曾抹掉 Portfolio BET 行**：specs/plans 仍在 tip，BET 行被 stale ledger squash 覆盖；已由 #3062 恢复 8 行。
2. **#3009 因未登记 script-registry 被关**：Wave A1 必须先落地 `portfolio_contract.yaml`，否则 GaC 拒收新 `bin/plan` 脚本。
3. **中途 Spec 1.0.1→1.0.2** 触发 `WORK_PACKET_SOURCE_DRIFT`：旧 run 只能 blocked，必须 fresh start 绑定新 digest。
4. **`meta.total_bets=149` vs `len(bets)=289`**：漂移 ~140；compat WARN 正确，strict 必须等单字段修复后再开。

## Q4 净增减

- 新文件 +3：`portfolio_contract.py`、`test_bet_portfolio_contract.py`、`portfolio_contract.yaml`
- `bet-ledger.py`：+~40 LOC（lazy import + `portfolio` 子命令）
- Spec / ledger 元数据小改；GaC 规则 / ADR：0
- 未纳入无关 `projects/omlxc` pointer drift

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **立刻**：独立 claim `docs/plans/3y-bet-ledger.yaml::meta.total_bets`，只改该字段到 `289`（或当时 `len(bets)`），再 `--strict` 全绿。
2. T1-05…T1-09 / T8-05 仍可能 `human_gate: true`——需 principal 放行后再推进。
3. 不要在未修 `meta.total_bets` 前对 full Ledger 开 strict（circuit_breaker）。
4. Portfolio BETs 仍在 `CMP-W0-PORTFOLIO-TRUTH`；父 BET T1-03 未 close。

## Closeout refs

- run: `20260904T074355Z-project-code-change-30805980`
- branch: `work/bet-y1q4-t1-04`
- human_gate release: 2026-09-04 principal Wave A1
