---
type: governance-waiver
id: waiver-2026-11-27-t360-ratio
created: 2026-11-27
granted_by: laowang (engineering-agent)
pr_numbers: [5643]
scope: check-governance-ratio / doc-governance (gac-local-gate)
expires: 2027-05-27
last-reviewed: "2026-11-27"
---

# Waiver — T360 canary 收口 ratio 红 (PR #5643)

## 红源定性

1. **check-governance-ratio**: 本 PR 全部为治理文档交付 (台账 done 入账 + 回执 +
   pitfall 立条 + retro), 无代码/测试面变更, check coverage 比例自然低于阈值 ——
   与 T356/T357/T358/T359 同族的 docs-only ratio 红, 非缺陷。
2. **doc-governance (warning_budget_exceeded)**: 18 个 waiver 老文档超 90d
   SLA (budget 10) —— 预存时间型红, 主仓 HEAD 同红, 非本 diff 引入;
   由 stale_review 清偿线 (#5642 已清偿 frontmatter 同族) 持续消化。

## 证据

- 主仓 HEAD 对照: 同红 (预存确认, git diff 本 PR 未触及 waiver 老文档)。
- verify 记录: 4 PASS + 1 FAIL (gac-local-gate), 其余门全绿。
- 治理链: run 20261127T022218Z-bet-execution-d4eda8cc, claim 5 路径全投影。
