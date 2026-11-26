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
  - 5620  # T10-355 refresh 声明镜像回填 + capability-sync 主仓直提债立案 (数据修正)
waiver_scope: PR #5620 single merge (refresh declaration mirror + debt registration)
---

# T10-355 ratio waiver — refresh 声明镜像回填 + 债立案

## Principal authorization

> 「继续推进优化吧」— 2026-11-26 会话, 对持续优化的全链授权; 本 BET 属
> 「refresh 日志断流」对账的自然延伸 (本会话立案本债), 裁定基于 spec 裁定表
> (债条目 decision_needed 的结构病修法仍需 owner 裁定, 本 PR 只立案不修)。

## Waiver 边界 (narrow)

- 仅豁免 PR #5620 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 为**数据修正 + 债立案**: services.yaml 声明镜像本机 plist 实测现实
  (T353 同族) + 一条新债登记, 无治理机制开发。
- 45.1%>40% 为 30d 滚动统计预存基线 (主仓干净 HEAD 同红), 与本 diff 无关。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。

## 背景

- 先例: waiver-2026-11-25-t353-ratio.md (#5562), waiver-2026-11-25-t354-ratio.md (#5586)。
- 连续第三个声明镜像/数据修正类 BET, 均为拉齐登记面与现实的诚实性修正,
  非治理机制开发。

## 后续动作 (非本 waiver 义务)

- cron 主仓直提结构病修法 (a/b/c 三选一) 待 owner 裁定后另开 BET。
