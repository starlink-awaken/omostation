---
schema_version: specification/v1
spec_version: 1.0.0
title: T7-06/T10-151 合入后评审缺陷校正
bet_id: BET-Y2Q1-T7-07
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-15
---

# T7-07 — 合入后评审缺陷校正

## 1. 问题

对 `7508c84540..12b01ad3c4` 合入窗口的评审发现 4 个 bug：

1. `approve(decision="退回")` 仍写 `status=approved`，`dispatch` 可发出退回公文。
2. `BET-Y1Q4-T10-151` 标 `done` 且证据 VERIFIED，但当前 `projects/omo` pin 不含 A8 实现。
3. 影子台账 `.omo/plans/3y-bet-ledger.yaml` 与 SSOT `docs/plans/3y-bet-ledger.yaml` 冲突。
4. 场景卡引用不存在的 `docs/journey-specs/health-gov-doc-cycle-workflow.yaml`。

## 2. 非目标

- 不在本 BET 内合入 omo A8 实现（只校正虚假 done；实现另开/续 T10-151）。
- 不改动 agora/cockpit 子模块指针。
- 不扩大卫健公文管线到 OA/外发网关。

## 3. 设计

### 3.1 批阅状态机

- `同意` → `approved`（可 `dispatch` / 导出）
- `退回` → `returned`（不可 `dispatch`；可重新 `draft_opinion`）
- `转办` → `registered`（回到可拟办，附批阅意见）
- `IncomingDoc.last_decision` 持久化最近一次决策；`dispatch` 要求 `status==approved` 且 `last_decision==同意`

### 3.2 治理收口校正

- T10-151：`done` → `in_progress`，清除虚假 VERIFIED/PROVEN evidence，保留设计文档。
- T10-146：若因子 BET 虚假完成而标 done，回退为 `in_progress` 并注明依赖 T10-151。
- 删除/停止跟踪 `.omo/plans/3y-bet-ledger.yaml` 影子台账。

### 3.3 旅程契约

补齐 `docs/journey-specs/health-gov-doc-cycle-workflow.yaml`，与场景卡 `journey_id` 对齐。

### 3.4 一致性修补

- 文种接受 `xh-letter` 并规范化为 `letter`。
- 校准叙述与缺陷注入对齐；verify 命令显式 `--with reportlab`。

## 4. 验收

- `PYTHONPATH=projects/domain-cartridges/health-gov uv run --with reportlab python -m domain.health_gov.test_doc_pipeline` exit 0
- 负例覆盖：退回后 `dispatch` 必须拒绝
- `docs/journey-specs/health-gov-doc-cycle-workflow.yaml` 存在且可被场景卡引用
- 台账中 T10-151 非 done；无 `.omo/plans/3y-bet-ledger.yaml` 跟踪副本
