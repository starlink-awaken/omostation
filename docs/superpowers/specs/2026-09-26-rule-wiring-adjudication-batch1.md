---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 规则接线收口批次一 — 42 条 CR-* 零引用的四态判定与别名映射
bet_id: BET-Y2Q4-T10-01
---

# BET-Y2Q4-T10-01 — 规则接线收口（批次一）

## 背景

DEBT-20260920-RULE-WIRING-DECL-EXEC-GAP（2026-09-19 巡查实证）：
`check-rule-wiring-coverage.py` 报 governance-checks 声明 86 / 未引用候选 **42**；
三个注册表 ID 词汇完全解耦（CR-X4-* / X1-C01 / X2-C05），工具无法区分
"已实现但换名"与"真未接线"，故只能报候选不能判 fail。债务关单前提 =
owner 逐条建立 ID 别名映射，之后 `--strict` 才可接入门禁。

## 目标（批次一，≥20 条）

1. 导出 42 条清单，逐条收集证据指针；
2. 四态判定（每条记 rationale）：a) 已实现换名 → 建别名映射
   （沿用 `CR-X1-AGENT-AUDIT.source_ref` 先例）；b) 真未实现 → 实现或立后续 bet；
   c) 过时 → 标弃用退役；d) 存疑 → 升级 owner 决策卡；
3. 别名映射落进 `governance-checks.yaml`（source_ref/alias 字段）；
4. 映射后重跑 coverage，未引用数可度量下降；
5. 债务 item 追加 history（**不关单**——批次二另立 bet 收 --strict 门禁 + 关单）。

## 写面

`.omo/_truth/registry/governance-checks.yaml`、`bin/gac/check-rule-wiring-coverage.py`
（如需暴露映射读取）、`.omo/debt/items/DEBT-20260920-*.yaml`（仅 history 追加）、
`docs/plans/**`（判定表）、`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。

## 验收（done_when 摘要）

1. 42 条清单导出，≥20 条完成四态判定且每条带 rationale 与证据指针；
2. 批内所有"已实现换名"条目的别名映射落地（source_ref 指向真实执行体 文件:行）；
3. coverage 重跑未引用数下降且数值记录；
4. 债务 history 追加本批结论；retro 固化"三注册表共享词根"命名规范建议。

## 红线

- **禁止**无执行体 文件:行 锚就标"已实现换名"（假闭环教训）；
- 本批次不得把 `--strict` 接成强制门禁（批次二的事）；
- 不得删除/改写既有规则语义，只允许加 source_ref/alias/status 标注。

## verify

- `python3 bin/gac/check-rule-wiring-coverage.py` → 未引用候选数 < 42（记录新值）
- `python3 bin/plan/bet-ledger.py lint` → 不引入新错误
- `make gac-local-gate` → exit 0
