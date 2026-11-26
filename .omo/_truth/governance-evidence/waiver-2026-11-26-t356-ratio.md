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
  - 5622  # T10-356 cron 主仓直提断根 (worktree + 自动 PR)
waiver_scope: PR #5622 single merge (cron publish-mode cutover + debt resolve)
---

# T10-356 ratio waiver — cron 主仓直提断根

## Principal authorization

> 用户拍板「a」— 2026-11-26 会话, 对债 CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT
> 三选一修法的明确裁定 (worktree + 自动 PR 化, 先例 #4858)。本 PR 是该裁定
> 的直接落地, 授权链完整。

## Waiver 边界 (narrow)

- 仅豁免 PR #5622 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 为**断根修复**: cron 命令链治理面变更 + 债 resolve, 核心代码腿是
  生成器 --publish 模式 (工具开发, 非治理机制开发)。
- 46.79%>40% 为 30d 滚动统计预存基线 (主仓干净 HEAD 同红, T353/T354/T355
  同族三连先例), 与本 diff 无关。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。
