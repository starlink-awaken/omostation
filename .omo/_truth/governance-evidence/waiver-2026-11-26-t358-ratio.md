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
  - 5630  # T10-358 管道吞 rc pitfall 立条 + mcptool note 订正
waiver_scope: PR #5630 single merge (pitfall entry + reconciliation note correction)
---

# T10-358 ratio waiver — pitfall 立条 + note 订正

## Principal authorization

> 用户「继续推进吧」— 2026-11-26 会话, 对 T357 终报遗留项的直接授权
> (pitfall 立条 + note 订正两件收尾打包)。

## Waiver 边界 (narrow)

- 仅豁免 PR #5630 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 为**避坑基因文档 + 声明面订正**: pitfalls 立条 (append-only 档案)
  + AGENTS §7 簇表同步 + mcptool note 与命令链对齐, 无治理机制开发。
- 46%+>40% 为 30d 滚动统计预存基线 (主仓干净 HEAD 同红, T353-T357 五连
  先例同族), 与本 diff 无关。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。
