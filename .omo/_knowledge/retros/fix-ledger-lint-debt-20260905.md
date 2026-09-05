---
schema_version: retrospective/v1
type: retro
title: 台账 lint 归零 — T8-04 spec_ref 修复 + T6-17/18/19 字段补全
bet_id: fix-ledger-lint-debt
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# fix-ledger-lint-debt 复盘

## Q1 实际耗时 vs appetite？

非台账 bet（豁免启动）。约 25 分钟（定位 25 个 lint 问题根因 + 4 处精确 Edit + 验证 + 提交）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| 台账 lint 归零（25 → 0） | PASS（`OK -- 321 bets, 11 tracks, no errors`） |
| T8-04 SPEC_FRONTMATTER_BET_MISMATCH 消除 | PASS（移除误含的 HITL spec 条目） |
| T6-17/18/19 缺字段/未知 track 消除 | PASS（补 track/appetite/goal/done_when/verify/workflow/write_surfaces） |
| gac-local-gate | PASS（57 checks ALL GREEN） |

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **T8-04 的 accepted_specifications 误含 HITL spec**：T8-04（Scene card bet/falsifier 补全）复制粘贴时把 HITL Proposal System 的 spec 条目带进了 accepted_specifications（带完整 content_digest/decision_ref）。HITL spec 的 frontmatter bet_id 是 BET-Y1Q4-HITL-01，与 T8-04 不匹配 → SPEC_FRONTMATTER_BET_MISMATCH。修复：移除该条目（T8-04 的 close_evidence/note 已记录 HITL 生产使用，无需在 accepted_specifications 重复引用）。
2. **T6-17/18/19（#3214 立项）用非标准候选格式**：缺 track/appetite/goal/done_when/verify/workflow/write_surfaces（用 objective/deliverables/workload_days 替代）。bet-ledger.py 的字段校验对 candidate 也强制（candidate 只豁免 spec binding，不豁免基础字段）→ 每个 8 个 ERROR。修复：重构为标准字段（track 归属 T6-SUBTRACT/T6-EVOLUTION，goal/done_when 从 objective/deliverables 映射）。
3. 并行 agent 的 grandfather 方案（改 HITL spec bet_id）未落地：其本地 commit（0e5c73590）未完全 push，origin/main 上 HITL spec bet_id 仍是 HITL-01。采用更干净的"移除错误引用"方案，不与 grandfather 冲突。

## Q4 净增减？

代码行 0 / 文件 0 / 规则 0 / ADR 0 / 脚本 0（ledger 45+/22-，纯字段重构）。

## Q5 下一个认领本 track 的 agent 需要知道什么？

- 台账 lint 现 0 errors；T6-17/18/19 已是合法 candidate 可认领。
- 新增 candidate 必须带标准字段（track/appetite/goal/done_when/verify/workflow/write_surfaces），勿用 objective/deliverables 简写格式。
- accepted_specifications 只放 frontmatter bet_id 与自身匹配的 spec。
