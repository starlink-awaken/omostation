---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T10-123
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-123 Documents 归档冻结收账 spec

## 1. 目标

5 大内容归档族只读冻结 + registry verified 标记 + rollback receipt。

## 2. 验收

1. migration-check ok:true errors:0, non_terminal 13→7。
2. 冻结摘要入库 docs/reports/documents-archive-freeze-summary.json。
