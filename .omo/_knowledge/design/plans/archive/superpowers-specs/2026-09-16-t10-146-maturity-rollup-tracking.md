---
schema_version: specification/v1
spec_version: 1.0.0
title: OMO Agent OS maturity-gap rollup — tracking and dependency ordering
bet_id: BET-Y1Q4-T10-146
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: '2026-09-16'
---


# OMO Agent OS maturity-gap rollup — tracking and dependency ordering

## Problem

2026-09-11 的全量复核发现 OMO Agent OS 有 6 处成熟度差距（持久化 Queue、AGE-v2
Cell 违反 SFOP 八律第3条、A6 Orca R0/A7 Multica AS0 准入验证工具链缺失、A8
外部事务生命周期未实现、A5 残留 3 处死引用）。BET-Y1Q4-T10-146 本身不直接产出
代码——它的范围是把这 6 处差距拆成独立子 BET（T10-147 至 T10-152）、维护它们
之间的依赖顺序，并在子 BET 全部收口前不允许自身单独标记完成。

## Scope

本 BET 是纯协调/汇总性质，没有独立的代码交付面；它的"实现"就是子 BET 拆分
本身（已完成）与子 BET 状态的持续追踪。截至本次更新：
- T10-147（持久化 Queue）：done
- T10-152（A5 死引用清理）：done
- T10-151（A8 外部事务生命周期）：in_progress（phase 1 完成，phase 2 spec 已就绪，
  见 `docs/superpowers/specs/2026-09-15-a8-omo-external-transaction-lifecycle-design.md`）
- 其余子 BET（AGE-v2 SFOP 违规、Orca R0/Multica AS0 工具链）状态见台账

2026-09-15 的 T7-07 复核（`.omo/_knowledge/retros/BET-Y2Q1-T7-07.md`）发现 T10-151
此前被误标 done（其"已实现"证据在当时的 `projects/omo` 指针下不可达），已回滚为
in_progress，并连带把父项 T10-146 从此前的错误 done 状态回滚。本 spec 把 T10-146
正式定位为 in_progress（而非 candidate），如实反映"汇总仍在进行、子 BET 未全部
收口"这一真实状态。

## Non-goals

- 不代表 T10-146 自身有独立于子 BET 之外的代码实现
- 不预判子 BET 的具体技术方案（各子 BET 有各自的 spec）

## Acceptance

T10-146 转为 done 的条件不变：6 个子 BET（T10-147 至 T10-152）状态均不再是
candidate（done 或有明确 blocked 原因并记录）。本 spec 的作用仅是让 in_progress
这个中间状态本身可被台账工具正确校验（accepted_specifications + completion_evidence
两项此前缺失，导致 `bet-ledger.py lint` 拒绝该状态转换）。

参考: `docs/reports/2026-09-15-a8-external-transaction-authoritative-review.md`,
`.omo/_knowledge/retros/BET-Y1Q4-T10-146.md`, `.omo/_knowledge/retros/BET-Y2Q1-T7-07.md`
