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

> **TL;DR**: Wave A1 落地 Portfolio v2 compatibility validator（全 spec §6 校验面）。`human_gate` 已由 principal 放行。pytest 18/18；`bet-ledger portfolio lint` exit 0（compat 模式对 `meta.total_bets` drift 出 WARN，不阻断）；`portfolio lint --strict` exit 1（typed ERROR 阻断，符合预期）。full-Ledger strict + `meta.total_bets` 单字段修复仍按 done_when 要求走独立 claim。

## Deliverables

- `bin/plan/portfolio_contract.py` — additive Portfolio v2 compatibility validator（重写：实体 ID 唯一性、跨实体引用存在性、metric shape、bet_type 枚举、boolean policy、ISO-8601 时间戳、typed error contract）
- `tests/test_bet_portfolio_contract.py` — 18 fixtures（valid v2 GREEN、各实体 duplicate/missing/invalid、引用缺失、shape 失败、strict RED/GREEN、bootstrap_unenforced 豁免、无副作用）
- `bin/_registry/scripts/governance/portfolio_contract.yaml` — GaC script-registry 授权
- `bin/plan/bet-ledger.py` — `portfolio lint [--strict]` CLI
- Spec bump `1.0.1 → 1.0.2`（registry write surface + authority note）
- Ledger：T1-04 `human_gate: false`；write_surfaces 增补 registry yaml；binding digest→1.0.2

## Q1 实际耗时 vs appetite？

Appetite 3 days。本轮实现+registry+verify ~2h（前置 attempt 产物可复用：validator 草稿、registry amendment）。validator 全量校验面扩展 + 18 tests 另加 ~1.5h。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| full v1 Ledger 在 v2 parser 下可读、既有 BET 语义等价 | PASS（compat lint OK，289 bets 语义不变） |
| valid v2 fixture + typed fail | PASS（pytest 18/18） |
| compat mode 对 meta.total_bets drift 出 typed warning、不阻断 v1 | PASS（`WARN META_TOTAL_BETS_DRIFT: declared=149 actual=289`） |
| focused fixtures strict meta.total_bets==len(bets) | PASS（fixture 覆盖） |
| **独立 claim** 修复 meta.total_bets → len(bets) | **DEFERRED**（validator 合并后下一 claim） |
| 单字段修复不改 BET object/status/binding/... | DEFERRED（随上条） |
| 修复后 full Ledger strict 全绿 | DEFERRED（随上条） |
| validator 无 import-time / filesystem write side effect | PASS（纯函数 + no-side-effect 测试） |

Verify 命令（台账登记）：

```
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml --with pytest python -m pytest tests/test_bet_portfolio_contract.py -q
# 18 passed

PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python bin/plan/bet-ledger.py portfolio lint
# OK -- Portfolio v2 compatibility contract (exit 0)

PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python bin/plan/bet-ledger.py verify BET-Y1Q4-T1-04 --execute
# exit 0；D0 8/9 surfaces OK，meta.total_bets 标记"未入库"（本 PR 范围内预期，DEFERRED）
```

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **前置会话遗留本地 commit `1c1a45904`**：validator 草稿 + registry + spec/plan + 5 tests 已在本 worktree 的本地 commit 中（未推远端，不在 origin/main）。本轮在授权边界内扩展而非重做，避免重复劳动。
2. **PASW 隔离校验 "SHA 不一致: projects/omlxc"**：root gitlink 695c9b5 ≠ .subtrees/omlxc 旧 HEAD 2eb067f（stale、clean、本地分支未上远端）。`git reset --hard` 到 gitlink SHA 后 claim 通过。
3. **claim 要求 affected-graph receipt**：`agent-workflow.py claim` 拒绝缺 affected-hash 的路径；必须先生成 `affected-graph-receipt-*.json`（`--changed-projects workspace-root`）再 `--affected-receipt` 传入。
4. **`meta.total_bets=149` vs `len(bets)=289`**：漂移 ~140；compat WARN 正确，strict 必须等单字段修复后再开。该字段本 PR 故意不动（D0 显示"未入库"是预期而非缺陷）。
5. **`.omo/locks/checkout-log.tsv`**：worktree claim 产生的运行时产物，不在 .gitignore，提交时必须显式排除。
6. **enforcement 语义**：`schema_state` 缺失（如 `portfolio_binding: {}`）应视为待强制（非豁免），只有显式 `bootstrap_unenforced` 才是豁免——初版 `schema_state not in (None, "bootstrap_unenforced")` 误豁免 `{}`，改为 `schema_state != "bootstrap_unenforced"`。

## Q4 净增减

- 净增（相对 HEAD）：`portfolio_contract.py` +~257（重写纯函数校验器）、`test_bet_portfolio_contract.py` +179（18 tests）
- 既有面（HEAD 已含，无新增）：registry yaml、spec/plan 文档、`bet-ledger.py` CLI 接线
- GaC 规则 / ADR：0；未纳入无关 `projects/omlxc` pointer drift
- 说明：Y1 为减法年，本次为 spec 强制的 additive validator（registry + 保护性测试是"保护量"），非膨胀。

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **立刻**：独立 claim `docs/plans/3y-bet-ledger.yaml::meta.total_bets`，只改该字段到 `289`（或当时 `len(bets)`），再 `--strict` 全绿。
2. T1-05…T1-09 / T8-05 仍可能 `human_gate: true`——需 principal 放行后再推进。
3. 不要在未修 `meta.total_bets` 前对 full Ledger 开 strict（circuit_breaker）。
4. Portfolio BETs 仍在 `CMP-W0-PORTFOLIO-TRUTH`；父 BET T1-03 未 close。
5. **提交纪律**：只 add `bin/plan/portfolio_contract.py`、`tests/test_bet_portfolio_contract.py`、`.omo/_knowledge/retros/BET-Y1Q4-T1-04.md`；`.omo/locks/` 必须排除；保持已有 commit `1c1a45904`（registry/spec/plan/ledger wiring）在 PR 历史中，不要丢弃。

## Closeout refs

- run: `20260904T101431Z-project-code-change-8f2d4d03`
- branch: `work/bet-y1q4-t1-04`
- human_gate release: 2026-09-04 principal Wave A1

## Addendum — meta.total_bets single-field repair (2026-09-04)

- Claimed path: `docs/plans/3y-bet-ledger.yaml::meta.total_bets`
- Change: `149 → 289` (= `len(bets)`); BET ids/statuses/bindings untouched
- Verify: `bet-ledger.py portfolio lint --strict` → exit 0 (no META_TOTAL_BETS_DRIFT)
- run: `20260904T081421Z-project-code-change-fea38c0e`

## Addendum — status done (2026-09-04)

- `completion_evidence.overall_state=delivery_accepted` (value_indicator_policy=false)
- merged_reachable_commit: `git://origin/main@d2106d5b86dbc03c1ffc1f148e1786c41b2d9a63` (#3072 tip after #3066)
- Downstream T1-05 human_gate released for sequential Wave A1
