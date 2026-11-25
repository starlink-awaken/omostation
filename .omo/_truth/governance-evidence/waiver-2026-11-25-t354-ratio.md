---
schema: md/v1
status: active
lifecycle: history
owner: principal
created: 2026-11-25
last-reviewed: 2026-11-25
type: workflow-waiver
value_indicator_policy: false
pr_numbers:
  - 5586  # T10-354 驾驶舱模板契约收口 (工程类, 非 governance-state-mutation)
waiver_scope: PR #5586 single merge (dashboard template contract closeout)
---

# T10-354 ratio waiver — 驾驶舱模板契约收口

## Principal authorization

> 「给你授权，你帮我处理吧」+「go」— 2026-11-25 会话, 对慢工清单的全链授权;
> 本 BET 属授权范围内的债收口执行 (DASHBOARD-TEMPLATE-CONTRACT-GAP,
> decision_needed 无 human_gate 标记, 裁定基于债条目自给判据)。

## Waiver 边界 (narrow)

- 仅豁免 PR #5586 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 为**工程类**: 写面 bin/panorama/assets/host/template.html (部署资产 SSOT)
  + 债条目收口; 不含 governance-state-mutation 类机制开发。
- 42.1%>40% 为 30d 滚动统计预存基线 (主仓干净 HEAD 同红), 与本 diff 无关。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。

## 背景

- 上一轮 T10-353 (#5562) waiver 已注明「下阶段 BET 偏工程类稀释占比」——
  本 BET 正是工程类 (模板资产面, 不进分类器治理路径), 但 30d 窗口尚需时间消化。
- 先例: waiver-2026-11-25-t353-ratio.md (#5562), waiver-2026-09-17-4019 (#3870)。

## 后续动作 (非本 waiver 义务)

- 持续偏工程类 BET 直至 ratio 自然回落 40% 以下。
