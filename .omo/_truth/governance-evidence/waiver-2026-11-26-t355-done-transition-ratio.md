---
schema: md/v1
status: active
lifecycle: history
owner: principal
created: 2026-11-26
last-reviewed: 2026-11-26
type: workflow-waiver
value_indicator_policy: false
pr_numbers:
  - 5639  # T10-355 done-transition 入账 (复测全绿 + delivery_accepted)
waiver_scope: PR #5639 single merge (ledger done-transition accounting)
---

# T10-355 done-transition ratio waiver — 台账入账

## Principal authorization

> 用户「继续吧。做能做的」— 2026-11-26 晚会话, 对收尾可做项的直接授权;
> done-transition 入账是 T355 主体交付 (PR #5620, 2026-11-26 早 merge) 的
> 合法收尾腿, 复测哲学 (#5618 先例) 逐条实测通过后入账, 授权链完整。

## Waiver 边界 (narrow)

- 仅豁免 PR #5639 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 为**台账收尾入账**: done_when 三条晚场复测全绿 (逐字段 assert /
  0 drift / debt 纪律 rc=0) + completion_evidence 矩阵 + retro 复测记录,
  无治理机制开发。
- 46%+>40% 为 30d 滚动统计预存基线 (主仓干净 HEAD 同红, T353-T359 七连
  先例同族), 与本 diff 无关。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。
