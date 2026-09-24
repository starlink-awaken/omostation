---
type: operations
status: active
owner: governance-agent
created: 2026-09-24
last-reviewed: 2026-09-24
scope: workflow-requirement-iteration-waiver
---
# Workflow Waiver Record

**Date**: 2026-09-23（三次交付）/ 2026-09-24（本记录 + 修正交付）
**Agent**: governance-agent
**Escape hatch**: `AGCP_REQUIREMENT_ITERATION_GATE=0`（`requirement-iteration start requires --bet`）
**用于**: workflow `start` 与 `closeout`（后者同样因无 bet 而断 vision→retro 链）

## Reason

ADR-0203 的 requirement-iteration 门要求 `start --bet <BET-ID>`，但 **3Y-BET-LEDGER 当时 448 条 bet 全部
`status: done`，开放数为 0**（`docs/plans/3y-bet-ledger.yaml` 实测），不存在可绑定的 bet。
因此这不是"跳过门禁图省事"，而是**台账耗尽后的结构性必然**：只要继续交付，就必须走豁免。

> 本记录同时是该空档的可审计报告（"只报告，不处置"）：台账规划权属 principal，Agent 未增删任何 bet。
> 在补充新 bet 之前，**后续每一次交付都会需要同类豁免**——这是需要 principal 决策的点，不该被 env 变量静默抹平。

## Authorized Work

| PR | merged SHA | 内容 |
|----|-----------|------|
| #4244 | `b229a77da` | Agent Brief `resolve-failing-gates` 时效性提示 |
| #4245 | `b7052a2a6` | 两条治理踩坑固化（PITFALL-GAT-011 + pattern） |
| #4246 | `5b1564662` | `docs/operations/claims-activation-checklist.md`（只读） |
| 本次 | PR 待登记 | 复盘 findings F1–F4 修正：豁免留痕、删除无消费方字段、Claims 数值指针化、修 `gen-knowledge-index.py` 前缀元数据丢失 + 重建知识索引 |

## User Confirmation

- "可以，依次推进吧"（授权按 #4 → #5 → #1 顺序推进）
- 既有常置授权链："pr 合并提交" / "我给你授权，推进吧"
- 复盘后选择："F1 补豁免留痕、F2 删死字段、F3 数值指针化、F4 补可发现性；F5 只报告不处置"

## Boundary

- Claims Authority 激活保持 fail-closed，未由 Agent 代办；#4246 仅为只读文档。
- 未补录价值记录（30 条门保持 NOT_PROVEN）；未做 weekly-review（principal-only）。
- 台账未改动。

## Follow-up

本记录自身的存在即是 F1 的修正：此前三次豁免只落在 `.omo/_delivery/*`（gitignored），git 上零痕迹，
而 `bin/gac/check-governance-ratio.py` 依赖可审计的 waiver 记录做治理配额计数。
