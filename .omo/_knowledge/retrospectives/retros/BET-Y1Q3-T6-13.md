---
bet_id: BET-Y1Q3-T6-13
date: 2026-08-20
lifecycle: history
last_updated: 2026-08-20
status: archived
owner: governance-team
title: BET-Y1Q3-T6-13 Retro — 归档 bin/bc-os/ 无外部引用的 speculative 脚本
type: retro
---

# BET-Y1Q3-T6-13 Retro — 归档 bin/bc-os/ 无外部引用的 speculative 脚本

## Q1 实际耗时 vs appetite

- appetite: 1 hour
- 实际耗时: ~1 个会话
- 偏差原因: 无显著超出；主要时间在确认 3 个脚本确实无外部调用。

## Q2 done_when 通过情况

| # | done_when | 状态 | 证据 |
|---|---|---|---|
| 1 | 3 个脚本从 bin/bc-os/ 移入 archive | ✅ | PR #1763 |
| 2 | gac-validate active_bin_scripts 不跌出基线 | ✅ | active_bin_scripts ≤ 420 |
| 3 | make gac-local-gate 全绿 | ✅ | 46 checks ALL GREEN |

## Q3 打假 / 与 plan 不符的事实

- 最初传闻 `bin/bc-os/` 有“10 个零引用脚本”，实际深度核查后只有 3 个（apple_mail_watcher、l3_smart_router、lifecycle_changer）在 bin/Makefile/scene-cards/journey 中无外部引用。
- `evolution_engine`、`signal_router`、`north_star_meter_v2` 仍有场景卡、runtime cron 分类或台账引用，保留不动。
- `test_evolution_engine.py` / `test_integration_e2e.py` 是其父脚本的测试，随父脚本保留。

## Q4 净增减

- 删除/归档 tracked 文件: 3 个
- 新增 archive 目录: 1 个
- 活跃 bin 脚本数: 减少 3 个
- 无新增 ADR/GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么

- 若后续发现被归档脚本仍有调用者，应立即从 `bin/_archive/bc-os-20260820/` 恢复。
- 剩余 bc-os 脚本（evolution_engine/signal_router 等）的清理需先确认运行时 wiring 已退役或迁移。
