---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-10 Closeout Retro — Portfolio v2 validator 全 §6 校验扩展
bet_id: BET-Y1Q4-T1-10
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T1-10 Closeout Retro

> **TL;DR**: Validator 代码与 18 tests 已在 tip main（#3095）；本轮只做 ledger closeout：`status candidate→done`、刷新 T10-04 引入的 `type: ssot` digest drift、重绑 `merged_reachable` 到 main squash SHA、同步 `meta.total_bets`。pytest 18/18；`portfolio lint` tip 红（无关 bet 债务，见 Q3）。

## Deliverables (already on tip)

- `bin/plan/portfolio_contract.py` — §6 全量校验面
- `tests/test_bet_portfolio_contract.py` — 18 tests GREEN
- `docs/superpowers/specs/2026-09-03-w0-portfolio-v2-validator-full-s6-design.md` — accepted Spec（T10-04 批量分类补了 `type: ssot`）
- `docs/plans/3y-bet-ledger.yaml` — T1-10 → done + digest/CE 对齐 + total_bets 同步
- `.omo/_knowledge/retros/BET-Y1Q4-T1-10.md` — 本 closeout retro

## Q1 实际耗时 vs appetite？

Appetite 2 days（实现面）。实现已在 #3095 合入；本轮 ledger closeout ~1h（digest 漂移解锁 start、claim、verify、status flip、PR）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| 全 §6 校验面由 18 tests 覆盖且全 GREEN | PASS（pytest 18/18） |
| valid v2 fixture 通过；缺失/重复实体 ID、错误引用、metric shape、枚举、boolean policy、时间戳均 typed fail | PASS |
| v1 兼容模式零语义变化（portfolio lint exit 0） | **TIP FAIL（无关债务）** — 见 Q3；T1-10 自身不在 error 列表 |
| strict 模式对 total_bets != len(bets) 出 typed error | PASS（fixture） |
| validator 无 import-time / 文件写副作用 | PASS |
| 新 bet 条目登记完成（total_bets 同步） | PASS（本轮 meta.total_bets → len(bets)） |

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **代码早已在 tip**：#3095 交付 validator；#3118 已写入 `completion_evidence.overall_state=delivery_accepted` + `done_at`，但 `status` 仍停在 `candidate`。本轮只补 status/meta/CE 引用卫生，不重写 validator。
2. **SPEC_DIGEST_MISMATCH 拦 start**：T10-04 `#3155` 批量分类给 Spec frontmatter 加了 `type: ssot`，declared digest `7125cff0…` ≠ tip `286d18b3…`。必须先对本 bet 做定点 digest 字面量刷新才能 `agent-workflow start --bet`。
3. **`portfolio lint` tip 红（exit 1，102 问题）**：债务在 T1-12 / T8-04 / T10-02 / T10-03 / T1-03..T1-09 / T8-02 / T9-01 等**无关 bet**（digest drift、缺 CE、SPEC_BINDING）。T1-10 **不在** error 列表。按 non_goals **不**批量修其他 bet。`bet-done-transition` 门禁只硬失败 `BASE_LEDGER_UNREADABLE` / `BET_DONE_*`；本 transition 以本 bet 的 CE matrix + digests 为准，不要求 tip-wide portfolio lint exit 0。
4. **`merged_reachable` 原绑 `9e81919c…` 非 origin/main 祖先**（squash 前分支 tip）。对象仍在 store（warn-only），本轮重绑到 main squash `4ab195f5514a4f8c27448f5c923087d59f7e5aeb`（#3118）。
5. **`meta.total_bets` (310) != `len(bets)` (311)**：本轮同步为 311。

## Q4 净增减

- Ledger：`status candidate→done`；spec/diff digest 刷新（2 处）；retro digest 刷新；`merged_reachable` 重绑；`meta.total_bets` 310→311；补 `retro` / `close_evidence` 指针
- Retro：closeout 5Q 更新（本文件）
- Validator / tests / Spec 正文：0（已在 tip；Spec 仅历史 `type: ssot`）
- 其他 BET：0（non_goals）

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. T1-10 validator §6 面已关闭。**不要**再以 T1-04/T1-10 名义扩展同一 validator。
2. tip `portfolio lint` 红是跨 bet 债务（尤其 T10-04 分类导致的大量 Spec digest drift）。单独认领 hygiene bet 再修；不要夹带进无关 closeout。
3. 再改 Spec/tests/retro 必须同步本 bet（及引用同文件的 CE）digest，否则 `start --bet` / CE 校验会红。
4. 父 bet T1-03 与其他 W0 child 各有独立合同。

## Closeout refs

- run: `20260905T022407Z-project-code-change-f34575bc`
- branch: `work/bet-y1q4-t1-10`
- verify: pytest 18 passed；portfolio lint exit 1（102 tip debts, T1-10 clean）
- CE merged_reachable: `git://origin/main@4ab195f5514a4f8c27448f5c923087d59f7e5aeb`
- prior delivery: #3095 / #3118
