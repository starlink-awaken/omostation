---
bet_id: BET-Y1Q3-T1-08
date: 2026-08-20
lifecycle: history
last-reviewed: 2026-08-20
status: archived
owner: governance-team
---

# BET-Y1Q3-T1-08 Retro — 退役 coordination-daemon 独立 clone 部署并迁移备份到 Workspace

## Q1 实际耗时 vs appetite

- appetite: 1 day
- 实际耗时: ~1 个会话
- 偏差原因: 无显著超出；主要时间用于确认旧 daemon 进程状态、crontab 路径与 runbook 一致性。

## Q2 done_when 通过情况

| # | done_when | 状态 | 证据 |
|---|---|---|---|
| 1 | crontab 日备指向 Workspace bin/gac/coordination_store.py | ✅ | `crontab -l` 显示 `cd "$HOME/Workspace" && python3 bin/gac/coordination_store.py --backup` |
| 2 | runbook 更新为退役状态并给出 Workspace 路径 | ✅ | PR #1765 (待合入) 更新 `docs/operations/coordination-recovery-runbook.md` status=retired |
| 3 | make gac-local-gate 全绿 | ⚠️ | 本 bet 相关检查通过；全局 gate 存在预存失败 (check-work-landed、root-directory-governance 的 `.deepeval`、bet-retro-due-check) 与本 bet 无关 |

## Q3 打假 / 与 plan 不符的事实

- 最初传闻需要「升级独立 clone daemon」，实际检查发现 `com.omostation.agent-tick-daemon` 已 unload，只有 `com.omostation.signal-poller` 活跃。
- 真正遗留债务是 crontab 日备仍指向退役的 clone 路径，以及 runbook 仍描述 active 部署模式。
- 未删除 `~/agents/coordination-daemon/ws` 目录（超出 workspace 范围，留作人工确认后清理）。

## Q4 净增减

- 删除/归档 tracked 文件: 0
- 新增/修改 tracked 文件: 2 (runbook + ledger)
- 系统配置变更: crontab 备份路径从 clone 改指 Workspace
- 无新增 ADR/GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么

- 若未来重新启用独立 clone 部署，需重新写 BET 并更新 runbook / crontab / LaunchAgent。
- `~/agents/coordination-daemon/ws` 目录若 30 天内无引用，可安全删除。
