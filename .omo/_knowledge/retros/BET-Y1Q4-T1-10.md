---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-10 Closeout Retro — Portfolio v2 validator 全 §6 校验扩展
bet_id: BET-Y1Q4-T1-10
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T1-10 Closeout Retro

> **TL;DR**: 将 T1-04 Wave A1 validator（97 行/5 tests，main #3066）扩展为 spec §6 全量校验面（272 行/18 tests）。T1-04 保持 done；本 bet 为 T1-03 父链下的 follow-up。pytest 18/18；`portfolio lint` exit 0（294 bets）；T1-04 evidence digests 已刷新保持 delivery_accepted。

## Deliverables

- `bin/plan/portfolio_contract.py` — validator 扩展：实体 ID 唯一性（vision/objective/KR/campaign/milestone/bet）、跨实体引用存在性（campaign_ref/objective_refs/kr_refs/parent_bet）、metric shape、bet_type 枚举、boolean policy、ISO-8601 时间戳、typed error contract
- `tests/test_bet_portfolio_contract.py` — 18 tests（valid v2 GREEN、duplicate/missing/invalid ID、引用缺失、shape 失败、strict RED/GREEN、bootstrap_unenforced 豁免、无副作用）
- `docs/superpowers/specs/2026-09-03-w0-portfolio-v2-validator-full-s6-design.md` — 本 follow-up 合同（bet_id=T1-10）
- `docs/plans/3y-bet-ledger.yaml` — 登记 T1-10（total_bets 289→294 同步）+ 刷新 T1-04 evidence digests
- `.gitignore` — 对齐 main 的 `.omo/locks/` 运行时锁规则

## Q1 实际耗时 vs appetite？

Appetite 2 days。实现+测试扩展 + workflow + evidence 刷新 ~3h（validator 主体来自前一 attempt 的重写，rebase 后收敛）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| 全 §6 校验面由 18 tests 覆盖且全 GREEN | PASS（pytest 18/18） |
| valid v2 fixture 通过；缺失/重复实体 ID、错误引用、metric shape、枚举、boolean policy、时间戳均 typed fail | PASS |
| v1 兼容模式零语义变化（portfolio lint exit 0） | PASS（294 bets OK） |
| strict 模式对 total_bets != len(bets) 出 typed error | PASS（fixture） |
| validator 无 import-time / 文件写副作用 | PASS（纯函数 + no-side-effect test） |
| 新 bet 条目登记完成（total_bets 同步） | PASS（289→294） |

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **T1-04 已在 main 完成**（#3066 Wave A1 + #3072 total_bets 修复 + #3085 self-binding 均已合入）。上个会话交付的 commit 已被 main 吸收为 `4f7d5ce1c`，导致 rebase 时 6 个前置 commit 被自动 drop（内容已 upstream）。
2. **validator 扩展没有现成 bet 载体**：T1-04 已 done、T1-07 是 migration 工具、T1-03 是 specs/plans。最干净载体是新建 follow-up bet（本 bet T1-10）。
3. **gitlink-ancestry 门禁拦截 push**：分支基于旧 main，13 个子模块指针「回退」实为假 diff。rebase 到 origin/main 后消除；rebase 过程因 T1-04 已合入而自动丢弃重复 commit。
4. **T1-04 completion_evidence digest 失效**：扩展 validator/tests/retro 后，T1-04 的 evidence sha256 不再匹配（done_at 晚于 grandfather cutoff 2026-08-30，不豁免）。必须在 ledger 刷新 tests+retro 的 digest，否则 main 上 T1-04 永久红。
5. **agent-workflow start 的 SPEC_FRONTMATTER_BET_MISMATCH**：复用 T1-04 spec 会因 frontmatter bet_id 不匹配失败；T1-10 必须有自己的 spec（bet_id=T1-10）。

## Q4 净增减

- `portfolio_contract.py`：main 97 行 → 272 行（+175，纯扩展无删除）
- `tests/test_bet_portfolio_contract.py`：5 → 18（+179）
- 新文件 +2：T1-10 spec、T1-10 retro
- `ledger`：+1 bet（T1-10）+ T1-04 evidence digest 刷新（tests+retro，7 处 sha256）
- `.gitignore`：+2（对齐 main）
- GaC 规则 / ADR：0；未纳入无关子模块 pointer

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. T1-10 已为 validator 全 §6 校验面。**不要**再以 T1-04/T1-10 名义重复扩展 validator。
2. 后续若启用 full-Ledger strict mode，需确认 T1-04 evidence（已刷新）与 T1-10 登记均就绪；strict 仍受 T1-04 合同边界约束。
3. 任何再改 `bin/plan/portfolio_contract.py` / `tests/test_bet_portfolio_contract.py` 的后续 bet，必须同步刷新引用它们的 completion_evidence digest（T1-04 / 后续 bet），否则 CI 红。
4. `.omo/locks/` 已被 .gitignore 覆盖（对齐 main），worktree claim 不再产生未忽略运行时文件。
5. 父 bet T1-03 未 close；T1-05/06/07/08/T8-05/T1-09 等 child 各有独立合同，需独立认领。

## Closeout refs

- run: `20260904T111928Z-project-code-change-a869d37f`
- branch: `work/bet-y1q4-t1-04`
- human_gate release: 2026-09-04 principal (T1-10)
