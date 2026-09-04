---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T7-01 复盘
type: retro
---
# BET-Y1Q1-T7-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 3 days。scene-card v2 schema（五档生命周期 + bet/falsifier 必填）约 2 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| schema 支持 draft/shadow/assisted/supervised/routine 五档 | ✅ 场景卡 lifecycle 字段 |
| shadow 档定义为"无业务副作用, 不需要业务确认" | ✅ |
| 新增必填字段 bet + falsifier | ✅ document-review.yaml: bet=BET-Y1Q1-T7-01, falsifier 填写 |
| validator 检查五档合法性与 falsifier 存在 | ✅ make scene-card-check |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **五档生命周期替代原「active/archived」二元**: 原 schema 只有 active/archived，无法表达渐进授权（shadow→assisted→supervised→routine）。v2 升级时已有卡片批量迁移（2026-08-07 记录）。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- scene-card v2 schema（五档 + bet/falsifier）
- bin/ssot/scene-card-review.py validator
- docs/scene-cards/ 批量迁移
- ADR-0387 (dual-track scene admission)

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 场景卡 lifecycle ∈ {draft, shadow, assisted, supervised, routine}，shadow = 无业务副作用。
2. bet + falsifier 必填，falsifier 是「若 X 期间无 Y 则场景无价值」式证伪声明。
3. 新增/修改场景卡必须过 make scene-card-check。
