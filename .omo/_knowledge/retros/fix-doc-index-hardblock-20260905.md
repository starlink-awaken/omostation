---
schema_version: retrospective/v1
type: retro
title: doc-index 硬阻塞修复 — t10-122 证据文件 SSOT owner/date
bet_id: fix-doc-index-hardblock
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# fix-doc-index-hardblock 复盘

## Q1 实际耗时 vs appetite？

非台账 bet（豁免启动）。实际 < 30 分钟（1 文件 2 行 frontmatter + 验证 + 提交）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| doc-index --check 根仓硬阻塞清零（3 → 0） | PASS（剩余 1 个在 runtime 子模块，并行 agent 处理中） |
| workflow verify | PASS（4/4：doc-ssot-lint / ssot-guardian / gac-local-gate / doc-claims-check） |

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **T10-04 已被并行 agent 完成**（PR #3155 合入，UNTYPED 125），我 claim 的 worktree 是多余动作。
2. **3 个 doc-index 硬阻塞中 2 个由 t10-122 合入引入**（danger-gate-approval 证据文件 type:ssot 却缺 owner/date）——T10-04 完成时是 0，t10-122 回归。
3. **runtime 子模块硬阻塞已由并行 agent 修复**（工作树含 last-reviewed 待提交）——我若改会撞车，只修根仓部分。

## Q4 净增减？

代码行 +2（frontmatter owner/last-reviewed 各 1 行）/ 文件 +0 / 规则 +0 / ADR +0 / 脚本 +0。

## Q5 下一个认领本 track 的 agent 需要知道什么？

- 并行 agent 交付 `type: ssot` 的**证据/审批文件**时，必须同时带 `owner` + `last-reviewed`（doc-index 硬阻塞）。
- 根仓 CI 的 doc-index 会扫子模块文件；子模块 frontmatter 修复未合入前，根仓 PR 会持续红——需要跨仓协调。
- GAT-006 应验第三次：动手前 claim-check + 查 main 最新，避免重复交付。
