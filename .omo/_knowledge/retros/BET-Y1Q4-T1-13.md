---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-13 Closeout Retro — Portfolio-status broker ownership
bet_id: BET-Y1Q4-T1-13
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T1-13 Closeout Retro

> **TL;DR**: Registered brokered ownership for `.omo/_control/portfolio-status.json`
> in mutation-surfaces; wired `--check-broker`. `broker_owns_portfolio_targets`
> returns `broker_ok`. Apply adapter remains `PORTFOLIO_BROKER_APPLY_NOT_WIRED`
> (circuit breaker / T1-08 boundary). No Ledger reverse write; no Markdown rewrite.

## Deliverables

- `.omo/_truth/registry/mutation-surfaces.yaml` — `portfolio-projection-control` brokered entry
- `bin/plan/portfolio_projection.py` — `--check-broker` CLI (prints `broker_reason`)
- Spec + ledger binding + closeout report

## Q1 实际耗时 vs appetite？

Appetite 1 day。实现+验证+closeout ~1–2h（ownership 登记 + CLI，无新 ingress 模板）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| mutation-surfaces 登记 portfolio-status.json 写主 | PASS |
| `broker_owns_portfolio_targets` 返回 ok | PASS（`broker_ok`） |
| dry-run 不因 `PORTFOLIO_BROKER_OWNER_MISSING` halt | PASS（`--check-broker` exit 0；`--apply-omo` 现为 `APPLY_NOT_WIRED`） |

Verify:

```text
$ python3 bin/plan/portfolio_projection.py --check-broker
broker_ok
```

pytest `tests/test_bet_portfolio_projection.py`: 8 passed.

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **无既有 OMO ingress 可复用写 portfolio-status**：按 circuit breaker 降级为 ownership 登记 + dry-run；`broker_ref` 指向 `bin/plan/portfolio_projection.py:apply_omo_via_broker`（apply 仍未授权）。
2. **Ledger expect 文案 “broker ok” vs 函数返回 `broker_ok`**：保持既有断言字符串；CLI 打印 `broker_reason`。
3. **`--apply-omo` 在 ownership 通过后仍 halt**：符合 T1-08 / 本 bet non_goal；ownership dry-run 路径是 `--check-broker`。

## Q4 净增减

- mutation-surfaces +1 brokered surface
- portfolio_projection.py：`--check-broker` 分支（无新 bin 脚本）
- Spec / retro / report / affected-graph receipt
- GaC 规则 / ADR：0；未改 Ledger 写回方向；未重写 W0 Markdown

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. Ownership 已绿；真正把 control/goals bytes 经 broker 原子写入需后续 bet（接线 apply adapter，不得直写 `.omo`）。
2. 不要把 `PORTFOLIO_BROKER_APPLY_NOT_WIRED` 当成回归；T1-13 只消除 `OWNER_MISSING`。
3. `--check-broker` 不依赖 ledger 文件存在；`--check` 仍会因 Markdown drift 报错——与本 bet 无关。
4. 后续若改 mutation-surfaces 的 portfolio 条目或 projection CLI，刷新本 bet / 下游 completion_evidence digest。

## Closeout refs

- run: `20260905T004704Z-governance-state-mutation-5b5f3bdf`
- branch: `work/bet-y1q4-t1-13`
- verify: `python3 bin/plan/portfolio_projection.py --check-broker` → `broker_ok`
