---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 规则接线批次二 — 15 条存疑规则处置（判定工作簿批准执行）
bet_id: BET-Y2Q4-T10-05
---

# BET-Y2Q4-T10-05 — 规则接线批次二

## 授权链

- 判定工作簿（2026-09-27 会话呈报 15 条 + 建议）→ principal 回复「继续吧」= 全按建议执行。
- 前序：批次一（BET-Y2Q4-T10-01，29→27）+ SH-4 别名解析器（#4337）。

## 目标

15 条存疑规则全部落处置（无遗留悬空）：

1. **接线（2 条，语料可证）**：CR-L0-PROTOCOLS-SSOT → `check-hardcoded-ports`
   （.github/workflows/port-registry-enforce.yml 调用，#4411）；x2-staleness → `staleness`
   （bin/compass_radar.py staleness 子分）。
2. **收窄声明（2 条）**：CR-EVIDENCE-SHA-FRESHNESS（声明收窄到 spec digest 口径）、
   CR-BIN-RETIREMENT-CHECKLIST（收窄到 quota-diff 层）——描述与实现对齐。
3. **弃用标注（3 条原则族）**：CR-P76-6-5 / CR-P77-2-1 / CR-P77-2-2 —— 注释标注
   deprecated（原则类不入 GaC 机器清单），不删条目。
4. **记录待决（8 条）**：CR-L4-DOMAIN-REGISTRY-FRESHNESS（service-registry-reality
   不在可执行语料，需 CI 接线后另接）、CR-EVIDENCE-DECLARED、CR-L2-TASK-DELIVERABLE、
   CR-L0-SSOT-PATH-NORM、CR-X1/X2-POLICIES-SSOT（并入 SH-4 权威注册表决策）、
   CR-GIT-STAGE-SUBMODULE-PIN —— 每条带证据与建议，落批次二文档。
5. 债务 DEBT-20260920 history 追加批次二进度；coverage 复跑记录。

## 写面

`bin/gac/registry-alias-map.yaml`、`.omo/_truth/registry/governance-checks.yaml`、
`docs/plans/`（批次二处置文档）、`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。

## 红线

- 声明条目不删除，弃用仅注释标注（可见性保留）；
- 接线别名必须语料可证（2 处证据）；
- `--strict` 门禁强制不在本批次（剩余未引用 >0，shadow 记录于 retro）。

## 验收（done_when 摘要）

1. 2 组接线落地，coverage 27→**25**；
2. 15 条处置全部落批次二文档（含 8 条待决的证据与建议）；
3. 收窄/弃用注释落 governance-checks.yaml；
4. 债务 history 追加；
5. retro 固化。
