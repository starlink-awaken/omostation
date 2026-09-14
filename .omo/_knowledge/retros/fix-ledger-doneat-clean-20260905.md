---
schema_version: retrospective/v1
type: retro
title: 台账 T8-14/T8-16 重复 done_at 清理
bet_id: fix-ledger-doneat-clean
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# fix-ledger-doneat-clean 复盘

## Q1 实际耗时 vs appetite？

非台账 bet（豁免启动）。约 15 分钟（2 处 done_at 清理 + 验证 + 提交）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| T8-14 重复 done_at 清理 | PASS（剩 1） |
| T8-16 重复 done_at 清理 | PASS（剩 1） |
| 全台账重复 done_at 清零 | PASS（T8-14/15/16 均单 done_at） |
| gac-local-gate | PASS（57 checks ALL GREEN） |

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **重复 done_at 是 T8 系列并行收尾的系统性缺陷**：T8-14/T8-15/T8-16 三 bet 都是 `done_at: 2026-09-05`（简短）+ `done_at: 2026-09-04 11:00:00+00:00`（完整）双值——同一 agent 批量收尾时的模式。本 PR 清 T8-14/T8-16（T8-15 上一 PR 已清），台账重复 done_at 现已清零。
2. 无其他新发现。

## Q4 净增减？

代码行 0 / 文件 0 / 规则 0 / ADR 0 / 脚本 0（仅删 2 行重复 done_at）。

## Q5 下一个认领本 track 的 agent 需要知道什么？

- 台账已无重复 done_at；若再见双 done_at 即为新收尾缺陷。
- 修改 ledger YAML 用精确 Edit（title + 上下文定位），勿用正则捕获组（曾误删 bet 头部块）。
