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
  - 5625  # T10-357 mcptool 直提断根 (共享库提炼) + 装重修复
waiver_scope: PR #5625 single merge (mcptool publish-mode cutover + install fix)
---

# T10-357 ratio waiver — mcptool 直提断根 + 装重修复

## Principal authorization

> 用户「go」— 2026-11-26 会话, 对 T356 终报「同族第二例 mcptool 直提断根 +
> 装重缺陷处置」的直接授权。本 PR 是该授权的直接落地, 授权链完整。

## Waiver 边界 (narrow)

- 仅豁免 PR #5625 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 主体为**工具链断根修复**: 共享库提炼 (DRY) + 两脚本接入 + 装重
  bugfix + cron 命令链换装, 非治理机制开发。
- 46.8%>40% 为 30d 滚动统计预存基线 (主仓干净 HEAD 同红, T353/T354/T355/
  T356 四连先例同族), 与本 diff 无关。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。
