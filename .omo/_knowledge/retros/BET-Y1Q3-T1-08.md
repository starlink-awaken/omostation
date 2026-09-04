---
title: BET-Y1Q3-T1-08 Retro — 退役 coordination-daemon 独立 clone 部署
type: retro
lifecycle: history
owner: laowang-agent
last_updated: 2026-08-20
created: 2026-08-20
related: []
---
---
bet_id: BET-Y1Q3-T1-08
date: 2026-08-20
last-reviewed: 2026-08-25
lifecycle: history
owner: unassigned
---

# BET-Y1Q3-T1-08 Retro — 退役 coordination-daemon 独立 clone 部署

## Q1 实际耗时 vs appetite

- appetite: 1 day
- 实际耗时: ~1h(并发接手完成)

## Q2 完成情况

全部 done_when 达成:

- ✅ crontab 日备改指 `~/Workspace/bin/gac/coordination_store.py`(原指向
  `~/agents/coordination-daemon/ws`),已实测 `--backup` 返回 integrity ok
- ✅ `docs/operations/coordination-recovery-runbook.md` 更新为退役状态,所有
  部署路径改指 Workspace
- ✅ LaunchAgent plist(`com.omostation.agent-tick-daemon`)ProgramArguments
  改指 Workspace 版脚本
- ✅ Workspace 的 bin/scripts 无 `coordination-daemon/ws` 残留引用
- ✅ signal-poller 早已 reload 到 Workspace 修复后代码(上一轮已处理)

## Q3 关键发现

- **BET ID 冲突陷阱**: 本轮最初以 BET-Y1Q3-T1-06 立项,但 main 已有同号 BET
  (aetherforge 双副本指针同步,status: done)。按 next-adr/next-bet 思路必须
  对照 origin/main 已用编号取 max+1,本 BET 改为 T1-08。
- **旧代码污染源确认**: 持续写脏 `.omo/_truth/registry/memory-os.yaml` 的
  是 coordination-daemon clone 里的 agent-tick-daemon(旧 MOSBeliefManager)。
  退役该 clone 后污染源消除。
- **部署路径分散**: cron + LaunchAgent + runbook 三处都引用 clone 路径,
  退役需三处同步改,单改一处会残留。

## Q4 遗留/后续

- `~/agents/coordination-daemon/ws` 目录本体未删除(仅退役引用),后续确认
  无进程/无 cron 引用后可物理清理。
- `~/agents/` 下其他 agent clone(如 kimi-cleanup-20260819)是否同样需要
  退役/归档,待评估。
