---
bet_id: BET-Y3H2-T7-01
date: 2026-08-20
lifecycle: history
last_updated: 2026-08-20
status: archived
owner: governance-team
title: BET-Y3H2-T7-01 Retro — 公文场景 routine (限格式类)
type: retro
---

# BET-Y3H2-T7-01 Retro — 公文场景 routine (限格式类)

## Q1 实际耗时 vs appetite

- appetite: 3 weeks
- 实际耗时: 未进入实质开发
- 偏差原因: 2026-08-19 用户确认不再借调国转中心，公文场景相关外部协作窗口关闭；作为前置依赖的 `BET-Y3H1-T7-01` 同步冻结，本 bet 在未启动前归档。

## Q2 done_when 通过情况

| # | done_when | 状态 | 说明 |
|---|---|---|---|
| 1 | calibration >= 0.85 且连续 100 次 | ❌ 未达成 | 无执行数据 |
| 2 | 预算上限明确 | ❌ 未达成 | 场景未进入设计 |
| 3 | 单次影响可逆 | ❌ 未达成 | 无动作白名单 |
| 4 | 白名单动作明确列举 | ❌ 未达成 | 未形成动作清单 |

> 本次 closure 属于**范围取消/外部阻塞**。routine 自动化的前提是 assisted 阶段积累足够校准，前置条件 `BET-Y3H1-T7-01` 冻结导致本 bet 无法继续。

## Q3 打假 / 与 plan 不符的事实

- 将公文场景直接规划为 3 年内第一个全自动动作类型，跳过了 assisted 阶段的实际校准验证。
- 对“格式类”公文与“内容敏感类”公文的边界划分停留在设想阶段，没有形成可审计的动作白名单。
- 外部人事条件是本 bet 最关键的隐性依赖，但在创建时未被识别为阻断风险。

## Q4 净增减

- 新增代码: 0 行
- 新增文档/场景卡: 0 个
- 新增治理资产: 本 retro 文件 + 台账 `blocked_reason`/`note`/`completed_at` 更新
- 删除/归档: 无
- 经验教训: routine 自动化不应作为独立 bet 提前规划，而应是 assisted 阶段成功后的自然收敛结果。

## Q5 下一个认领本 track 的 agent 需要知道什么

- 公文场景 routine 化已随国转中心协作窗口关闭而冻结，**当前不应投入任何自动化实现**。
- 若未来重启，必须先重新评估 `BET-Y3H1-T7-01` 或新建前置 assisted bet，积累至少 100 次真实人机协作记录后再考虑 routine。
- 本 retro 与 `BET-Y3H1-T7-01` 共同构成“外部协作窗口关闭”案例对，建议写入场景 bet 风险评估模板。
