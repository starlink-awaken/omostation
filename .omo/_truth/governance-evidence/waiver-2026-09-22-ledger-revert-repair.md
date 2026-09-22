---
schema_version: governance-waiver/v1
created: '2026-09-22'
bet_id: unbound
run_id: 20260922T103331Z-governance-state-mutation-ba5e48ce
scope: ledger-revert-repair-managed-successor
---

# Waiver · Ledger 回退修复（无 bet 绑定）

## 背景

PR #4201（merge `5a3d980cd`）从陈旧分支 squash 合并，对
`docs/plans/3y-bet-ledger.yaml` 造成三处对 main 真值的回退（PITFALL-GAT-006
复发实例）：

1. `BET-Y2Q2-T10-154`：`done` → `blocked`，`done_at` 被删，operational 证据
   由 PROVEN 退化为 DEGRADED 且 receipt 键被改写；
2. `BET-Y2Q2-T155`（`BET-Y2Q2-T10-155`）：整条目被删除；
3. `meta.total_bets`：`443` → `439`（派生字段重新漂移）。

本 PR 以 `169aef1ce`（#4201 的合并基）中的已知良好块为真值源，恢复 1、2 两处，
并按合并时 `len(bets)` 重新派生 3。#4201 对 T5-02/T5-03 自身的证据细化不属于
回退，保留不动。

## 豁免理由与机制

台账回退修复是对治理数据的事务性写操作，不对应任何台账 bet（全部 441+ done，
无 in_progress 候选可绑定）。按 PITFALL-GAT-009 固化路径，使用
`governance-state-mutation` workflow；`start` 阶段无 bet 可用，故使用文档化的
一次性前缀 `AGCP_REQUIREMENT_ITERATION_GATE=0`（closeout 阶段该 workflow 具备
G8 治理豁免，无需再次前缀）。默认门禁在其余维度保持生效。

## 验证

- `python3 bin/plan/bet-ledger.py lint`：本 PR 触达条目（T10-154 / T10-155 /
  `meta.total_bets`）零新增问题。
- 残留 3 条 ERROR 全部属于 `BET-Y1Q3-T10-114`（其 `tests` / `replay` receipt
  指向被 #4205/#4207 归档清理删除的测试文件），为本 PR 基线（`ec3351676`）上
  的预存债务，非本次引入；已在本 waiver 与 PR body 中如实披露，归 #4205/#4207
  所属 lane 后续处理。

## Successor 说明

首版交付在 `agent/governance-agent/ledger-revert-repair-4201`（commit
`8bf4596d0`）因 submit 的 MANAGED_SUCCESSOR_REQUIRED 政策（origin/main 前进时
禁止陈旧基合并）转为 proposal-only；本 PR 为按政策在最新基上的托管后继重放。
