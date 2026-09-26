---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 治理降档 ADR — closeout/retro 分级与 docs+chore 占比回落机制
bet_id: BET-Y2Q4-T6-01
---

# BET-Y2Q4-T6-01 — 治理降档 ADR（human_gate: true）

## 背景

近 30 天 docs+chore 提交占比 45%，贴 40/40/20 治理预算红线（ADR-0249）；
closeout 文档对所有 BET 等级统一强度，边际收益递减。治理基建已建成
（BET 完成 99.6%、12/12 域 Harness 绿），应进入"降档不降纪律"的消费期：
**分级只影响文档密度，三轴证据门禁不动**。

## 目标

1. 起草 **ADR-0456**：分级方案（P0/P1 全量 closeout + retro；P2 及以下轻量模板）、
   before/after 文档强度数字、风险评估、回滚方案；
2. 标准修订提案：`.omo/standards/` 中 closeout/retro 相关条款的分级 delta；
3. shadow 方案：前 10 个关闭 bet 双轨对比（全量 vs 轻量）的审计质量抽检计划；
4. **human gate**：ADR 合入前须 principal 显式批准（decision_ref 记录批准）。

## 写面

`.omo/_knowledge/decisions/**`、`.omo/standards/**`（提案级 delta）、
`docs/**`、`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。

## 验收（done_when 摘要）

1. ADR-0456 完稿（含数字基线 45% → 目标 ≤35%、分级判据、回滚）；
2. 标准 delta 提案文档就绪（不直接改强制条款）；
3. shadow 对比计划（10 bet 样本、抽检判据）成文；
4. 人类批准的 decision_ref 落 ADR（或如实记录 pending 状态关 blocked）；
5. retro。

## 红线

- **强制执行前必须有人类批准** —— 批准缺失只能关 blocked 或 pending，不得自行生效；
- 三轴证据矩阵（engineering/operational/value）的 REQUIRED 键集不得减少；
- 不得顺带清理/归档任何既有 retro（那是历史证据）。

## verify

- ADR 文件存在且含 before/after 数字与回滚节
- `python3 bin/plan/bet-ledger.py lint` → 不引入新错误
- `make gac-local-gate` → exit 0
