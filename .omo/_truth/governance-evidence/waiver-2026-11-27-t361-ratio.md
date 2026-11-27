---
schema: md/v1
status: active
lifecycle: history
owner: principal
created: 2026-11-27
last-reviewed: 2026-11-27
type: workflow-waiver
value_indicator_policy: false
granted_by: laowang (engineering-agent)
pr_numbers:
  - 5653
waiver_scope: PR #5653 single merge (T361 pitfall 立条 —— YAML 手术纪律 + 已修复三连闸)
expires: 2027-05-27
---

# Waiver — T361 pitfall 立条 ratio 红 (PR #5653)

## 红源定性

1. **check-governance-ratio**: 本 PR 全部为治理文档交付 (pitfalls 两则 +
   AGENTS §7 短语 + 台账 T361 登记 + spec + retro), 无代码/测试面变更,
   check coverage 比例自然低于阈值 —— 与 T356~T360 同族 docs-only ratio 红。
2. **doc-governance (warning_budget_exceeded)**: waiver 老文档超 90d SLA
   超预算 —— 预存时间型红, 主仓 HEAD 同红, 非本 diff 引入。

## 证据

- 主仓 HEAD 对照: 同红 (本 PR 未触及 waiver 老文档)。
- 治理链: run 20261127T051533Z-bet-execution-453872a0, claim 4 路径全投影。
- 手术三验: yaml OK + 全表 digest 非法 0 + diff 量级对拍 39+/1-。
