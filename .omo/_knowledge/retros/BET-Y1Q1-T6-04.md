---
lifecycle: history
owner: governance-team
bet: BET-Y1Q1-T6-04
last_updated: 2026-08-16
title: BET-Y1Q1-T6-04 复盘
type: retro
---

# BET-Y1Q1-T6-04 复盘

## Q1 实际耗时 vs appetite？
Appetite 1 day。在已有 `work/bet-y1q1-t6-02` 上跟进，未另开 T6-03。

## Q2 done_when
- 感知取最近关闭 bet：是（`run_recency_key` + 测试 `test_perception_prefers_latest_closed_bound_run`）
- T6-03 复盘不再写 #1555 blocked：是（记录 `82f42e31d`）
- `verify --execute` 看退出码：是（`_run_verify_cmd`）
- verify 命令不依赖 gitignore digest：是（断言 `redlines.yaml` + 生成器源码）

## Q3 打假
- T6-03 已 done，本轮登记 T6-04，没有静默重开。
- #1555 在复盘文件过期时其实已经 MERGED；文档谎言比代码洞更危险。
- T6-03 两条 run 仍是 `blocked` 不是 `ok`——合入 main ≠ ok closeout。
- 共享 `~/Workspace` 仍落后 origin/main，不能当主干看。

## Q4 净增减
- 根仓：感知排序 + ledger verify 退出码 + 测试 + 指针 + T6-04 台账/复盘
- GaC required：+0
- ADR：+0
- 第四套 ID：没有

## Q5 下一个 agent
不要再给 T6-02/T6-03/T6-04 加写面。D0 tag 与 PR 合入是收口。submit 自动 wip、D3/D5 仍非本轨。

## 2026-08-16 洞对照

| 洞 | 状态 | 指针 |
|---|---|---|
| #1555 未进 main | **fixed** | squash `82f42e31d` |
| T6-03 retro 仍写 blocked | **fixed** | `.omo/_knowledge/retros/BET-Y1Q1-T6-03.md` |
| 感知文件名第一 | **fixed** | `chain_bind.perception_fields` / `run_recency_key` |
| verify --execute 假绿 | **fixed** | `bet-ledger._run_verify_cmd` |
| T6-03 verify 依赖 gitignore digest | **fixed** | ledger verify 改断言源码面 |
| T6-02/T6-03 `pr:` 空 | **fixed** | `#1547` / `#1555` |
| T6-03 D0 tag | **deferred** | 本轮随 T6-04 tag 一并钉 |
| T6-03 run 为 blocked 却标 done | **honest gap** | 不改写历史 run |
| submit 自动 wip | **deferred** | non_goal |
| D3/D5 / gbrain+kairon | **deferred** | grill 未授权 |
