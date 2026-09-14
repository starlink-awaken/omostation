---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T1-14 Closeout Retro — Portfolio OBJ-VALUE + 3 KR registration
bet_id: BET-Y1Q4-T1-14
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T1-14 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 0.5 day vs 1 day appetite。未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
本 PR 完成 OBJ-VALUE / 3 KR / CMP-Y1-VALUE-PROOF / 5 candidate bet 写入与 Spec 绑定。
正式 `bet-ledger complete` 可在 PR 合入 tip 后用 squash SHA 补 completion_evidence。

## Q3 过程中发现的与 plan 不符的事实（打假）？
1. `start --bet` 对 candidate 仍强制 SPEC_BINDING + specification/v1 frontmatter。
2. 不可把新 KR 标 `required: true`，否则 `NONTERMINAL_BET_UNBOUND` 会波及全仓未绑定 candidate。
3. tip 上 portfolio coverage 仍有历史 `DEPENDENCY_REF_MISSING`（T1-12→PR-*）与 KR duplicate rationale，与本拆分正交。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
+1 objective / +3 KR / +1 campaign / +5 bets；+2 docs（spec+report）；+1 retro。无新 GaC 规则/ADR/脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
先合入本 PR，再认领 T4-02/03/04（依赖 T1-14）。产品咽喉仍是 T10-105（真实 Diff 样本）。T8 DX 不要插队。
