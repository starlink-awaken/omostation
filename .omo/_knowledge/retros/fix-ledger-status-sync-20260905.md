---
schema_version: retrospective/v1
type: retro
title: 台账 status 收口 — 3 个已交付 bet candidate→done
bet_id: fix-ledger-status-sync
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# fix-ledger-status-sync 复盘

## Q1 实际耗时 vs appetite？

非台账 bet（豁免启动）。约 30 分钟（3 处 status 修正 + 1 处重复 done_at 清理 + 验证）。

## Q2 done_when 是否全部通过？

| 条目 | 结果 |
|------|------|
| T1-10 / T8-15 / HITL-01 status: candidate → done | PASS |
| T8-15 重复 done_at 清理 | PASS |
| gac-local-gate | PASS（57 checks ALL GREEN） |
| bet-ledger lint | 236 既有问题（含 2 个本修改暴露，非阻塞） |

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **T8-15 其实已 done**（并行 agent 已修 status），本次实际只改 HITL-01 + T1-10 两个；且 T8-14/T8-15/T8-16 **三个 bet 都有重复 done_at**（并行收尾时的系统性小缺陷，本次只清 T8-15）。
2. **HITL-01 / T1-10 改 done 会暴露 completion_evidence 债**：HITL-01 缺 completion_evidence 块（COMPLETION_EVIDENCE_REQUIRED），T1-10 的 merged_reachable_commit ref 在 object store 不可达（历史 commit 失效）。均为**既有债**（并行 agent 收尾不完整），不阻塞 gac-gate。
3. **正则批量修改 ledger 有破坏风险**：首次用 Python 正则改 status 时误删了 bet 头部块（id/title 等），已回滚改用精确 Edit 完成。教训：**台账 YAML 修改必须用精确文本定位（Edit），避免正则捕获组误匹配**。

## Q4 净增减？

代码行 0 / 文件 0 / 规则 0 / ADR 0 / 脚本 0（仅台账 status 字段值变更）。

## Q5 下一个认领本 track 的 agent 需要知道什么？

- 台账 candidate 且带 done_at/note 的 bet = **已交付未收口**，可直接 status→done（先查 main 交付物 + retro 确认）。
- completion_evidence 债（HITL-01 缺块、T1-10 ref 失效）待后续补齐；不阻塞 gate。
- **改 ledger YAML 用精确 Edit，不用正则捕获组**（T8-14/T8-16 的重复 done_at 也可用同样方法清理）。
