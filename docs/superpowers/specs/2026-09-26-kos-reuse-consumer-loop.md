---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: KOS 复用消费端闭环 — kos-cold-start 端到端验证与命中证明
bet_id: BET-Y2Q4-T3-02
---

# BET-Y2Q4-T3-02 — KOS 复用消费端闭环

## 背景

KOS 索引健在（`data/kos/kos-index.sqlite`，12,553 篇，当日更新；扩量任务
KOS-Q-GROWTH-ROLLING 记录 measured_documents=5193 → 实测已翻倍），但**消费端未证明**：
`kos-cold-start` skill 依赖 `mcp-server-kos`（query_custom_sql / search_kos / list_entities），
其挂载状态与端到端命中能力未验证。知识"只生产不消费"，复利未发生。

## 目标

证明冷启动复用回路端到端可走通：新会话按 skill 三步执行，产出
（BRIEF 路径、≥3 条相关 ADR 命中、实体样本）留档；若 MCP 未挂载或命中失败，
在允许写面内修复 skill/文档并如实记录缺口；挂载若需动 `config/**` 则只出提案不动手。

## 写面

`.agents/skills/kos-cold-start/**`、`docs/**`（验证记录/提案）、
`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。

## 验收（done_when 摘要）

1. 端到端运行记录：三步各步输出留档（BRIEF 路径解析、ADR 命中 ≥3、实体样本）；
2. MCP 未挂载时的处置：挂载提案文档 + skill 文档更新至真实状态（不虚报可用）；
3. skill 触发条件/文档与实际流程一致；
4. retro 附命中证据（引用命中条目的 doc_id/title）。

## 红线

- 不得编辑 `config/**`（机器身份）——只出提案；
- 不得修改 kos-index.sqlite 数据或重跑全量索引；
- 不得把"命中 0 条"包装成通过（D1）——0 命中是失败，如实关 blocked 并记录原因。

## verify

- 依 skill 文档执行三步并留档输出（命令 + 结果摘录）
- `python3 bin/plan/bet-ledger.py lint` → 不引入新错误
- `make gac-local-gate` → exit 0
