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
  - 5636  # T10-359 现实对账第一批 (resident sync-reality + fullrefresh 复活 + 双债立案)
waiver_scope: PR #5636 single merge (reality reconciliation batch 1)
---

# T10-359 ratio waiver — 现实对账第一批

## Principal authorization

> 用户「继续吧，全部推进」+「继续吧」— 2026-11-26 会话, 对四线收口
> (T279 核实 / 归档区处置 / reality 预存债 / god-module) 的全量授权;
> fullrefresh 恢复启用与 god-module backlog-first 经 AskUserQuestion
> 双裁定。本 PR 是该授权的直接落地, 授权链完整。

## Waiver 边界 (narrow)

- 仅豁免 PR #5636 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 为**声明-现实对账 + 债立案**: cron registry 三条 sync-reality
  (工具通道原子回写) + 双债登记 + 台账卫生 (T356-358 补 done_when/
  completion_evidence), 无治理机制开发。
- 46%+>40% 为 30d 滚动统计预存基线 (主仓干净 HEAD 同红, T353-T358
  六连先例同族), 与本 diff 无关。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。
