---
bet_id: BET-Y3H1-T7-01
date: 2026-08-20
lifecycle: history
last_updated: 2026-08-20
status: archived
owner: governance-team
title: BET-Y3H1-T7-01 Retro — 中试 / 政策申报升 assisted
type: retro
---

# BET-Y3H1-T7-01 Retro — 中试 / 政策申报升 assisted

## Q1 实际耗时 vs appetite

- appetite: 4 weeks
- 实际耗时: 未进入实质开发
- 偏差原因: 2026-08-19 用户确认不再借调国转中心，政策申报相关外部协作窗口关闭，场景在未启动实施前被冻结归档。

## Q2 done_when 通过情况

| # | done_when | 状态 | 说明 |
|---|---|---|---|
| 1 | calibration >= 0.6 | ❌ 未达成 | 场景未进入执行，无校准数据 |
| 2 | lifecycle=assisted | ❌ 未达成 | 场景直接冻结，未建立 assisted 工作流 |
| 3 | 至少一次真实申报使用了系统产出 | ❌ 未达成 | 外部条件消失，无真实申报机会 |

> 本次 closure 属于**范围取消/外部阻塞**，而非 done_when 全部达成后的正常交付。台账已标记 `blocked_reason` 与 `note`，并归档为历史参考案例。

## Q3 打假 / 与 plan 不符的事实

- 该 bet 建立在“用户持续借调国转中心”这一隐性假设上，但未在 depends_on 或 risk 中显式绑定外部人事条件。
- 当外部条件变化时，不存在 graceful 降级路径：既不能推进到 assisted，也无法转为 routine，只能冻结。
- 场景卡片 `docs/scene-cards/v2/` 中尚未产生与本 bet 直接相关的持久资产，因此无代码/文档需要迁移。

## Q4 净增减

- 新增代码: 0 行
- 新增文档/场景卡: 0 个
- 新增治理资产: 本 retro 文件 + 台账 `blocked_reason`/`note`/`completed_at` 更新
- 删除/归档: 无
- 经验教训: 长期依赖外部人事/组织窗口的 bet，应在创建时就声明“外部条件假设”与“取消触发器”。

## Q5 下一个认领本 track 的 agent 需要知道什么

- 国转中心政策申报场景已正式冻结，**勿在未经用户确认的情况下重启**。
- 若未来用户重新借调或出现新的政策申报场景，应新建 bet 而非复活本条目。
- 本 retro 与 `BET-Y3H2-T7-01` 公文场景共同构成“外部协作窗口关闭”案例对，可用于后续场景 bet 的风险评估模板。
