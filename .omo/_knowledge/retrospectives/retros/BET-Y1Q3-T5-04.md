---
title: BET-Y1Q3-T5-04 复盘 — SR-06 四缺口修复
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  T1-18 retro Q3 记录的四个产品缺口, 本轮全部修复。全部为 fail-closed 误伤
  (防御正确但拦了不该拦的), 修复不改语义只修误伤路径。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T5-04 复盘

## 四缺口对照 (2026-08-16)

| # | 缺口 | 修复 | 测试 |
|---|---|---|---|
| 1 | admission TTL × mesh 幂等死锁 | `AdmissionRenewed` 事件 (EVENT_STATE 自环 dispatched→dispatched) + `renew_admission()` (终态拒绝/身份校验/幂等键) | roundtrip: 续期成功+身份不匹配拒 |
| 2 | worker 空 filesModified 致 collect 误拒 | prompt 契约层强制条目 (非空数组, 空=unproven 不收 candidate) | 契约文本断言 |
| 3 | gitignore 区越界写不可见 | collect 补 `ls-files --others --exclude-standard` 扫描 (.omo/workers/runs 豁免) | 扫描调用断言 |
| 4 | terminal fallback 200 行截断 | `ORCA_TERMINAL_READ_LIMIT` 环境变量 (默认 800) | env 键断言 |

## 验证

- 新测试 5/5；回归 86/86 (workflow_mesh + blueprint_control 全量)
- ruff 全绿（存量对照零新增）

## Q3 设计取舍

- gap-1 走「自环新事件」而非「改幂等键」：后者会破坏 requested 事件的唯一性语义，前者零迁移
- gap-2 走契约层而非 supervisor 判定放宽：filesModified 空本就异常，从源头要求比末端放行正确
- gap-4 走环境变量而非硬编码提升：不同 worker 输出量差异大，运维可调比拍数字好

## Q5 给下一个 agent

- `renew_admission` 的调用入口还没接 CLI——下轮 supervised execute 失败重试时应自动调用（当前手动）
- gap-3 的豁免清单 (.omo/workers/runs) 若 review note 要纳入越界检测，需重新设计豁免粒度
