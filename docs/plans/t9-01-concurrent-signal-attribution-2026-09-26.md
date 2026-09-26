---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: ephemeral
title: "并发冲突 12 信号逐个归因表（BET-Y2Q4-T9-01）"
---

# 并发冲突信号归因表（2026-09-26，BET-Y2Q4-T9-01）

> 快照来源：`.omo/state/health.yaml`（2026-09-26T09:47Z）`concurrent_conflicts: 12`，
> 执行面 4/100（12 × 权重 8 = 96 扣分）。溯源工具：`_count_concurrent_conflict_signals`
> （bin/compass_radar.py:220）＝ **run_pressure + wt_pressure**。

## 1. 构成分解（信号 = run_pressure + wt_pressure）

| 分量 | 定义 | 实测 | 判定 |
|---|---|---|---|
| run_pressure | max(0, distinct status=active run − 1)，主 checkout runs 目录 | 70 个 run 记录，**0 个 active** | **0** —— N1 治本（orphan prune + 按 run status 计数）生效，无陈旧活跃 run |
| wt_pressure | max(0, git worktree 总数 − 2) | 快照时 14 − 2 = **12** | **12** —— 全部来自 worktree 扇出 |

**结论：12 = 100% wt_pressure，零假信号。** 复测时（同日 20:1x）worktree 已回落到
12 个 → wt_pressure = 10（并发 agent 自己释放了 2 个），信号随真实负载**自行愈合**。

## 2. worktree 逐个归因（复测时点，12 个注册）

| # | 最后活动 | 脏文件 | 分支 | 处置 | 理由 |
|---|---|---|---|---|---|
| 1 | 09-26 | 18 | (main) | **保留** | 主 checkout（免费额度） |
| 2 | 09-26 | 0 | bets-y2q4-t9-01 | **保留** | 本 bet 自身 worktree（免费额度） |
| 3 | 09-26 | 0 | sh67-brief-and-canonical | 保留 | 并发 agent 今日活跃（SH-6/7 主线） |
| 4 | 09-26 | 22 | doc-governance-20260926 | 保留 | 并发 agent 今日活跃 |
| 5 | 09-26 | 4 | bet-y2q4-t4-01 | 保留 | 并发 agent **已认领我铸造的 T4-01** 并开工——三信号检查实证有效 |
| 6 | 09-26 | 0 | state-sync-20260926 | 保留 | 并发 agent 今日活跃 |
| 7 | 09-26 | 18 | ws-devruntime-b1 | 保留 | 并发 agent 今日活跃 |
| 8 | 09-26 | 1 | fix/gateway-endpoint-bin（/private/tmp） | 保留 | 开放 PR #4388 的工作树，活跃 |
| 9 | 09-26 | 0 | fix/gateway-consumers-bin（/private/tmp） | 保留 | 同上 |
| 10 | 09-23 | 7 | north-star-first-decision-episode（.codex） | 保留 | **带 7 个未提交 WIP**——删除即毁他人现场（红线） |
| 11 | 09-23 | 0 | DETACHED（.codex） | 保留 | 干净但属 codex 会话基底，非本 bet 处置对象 |
| 12 | 09-24 | 8 | north-star-worktree-safety-20260924-01（.codex） | 保留 | 带 8 个未提交 WIP |

**可清理残留：0。** 快照 12 → 复测 10 的回落由并发 agent 自行释放，非本 bet 处置。

## 3. 结构性发现（归 owner 决策，本 bet 不动）

`wt − 2` 的免费额度假设「常态 = 主 + 1 个活跃 worktree」，但本仓自 40/40/20 预算与
多 agent 并发作业成为常态后，**日常在飞 worktree 稳定在 8–11 个**。结果是该信号
在任意工作日恒报 ~8–12、扣 ~64–96 分——**已饱和为常数扣分，信息量为零**
（无法区分"真冲突日"与"正常忙碌日"，D6 反身性）。且它把"并发"与"冲突"混为一谈
（代码注释自认 soft signal）。

**候选方案（owner 拍板，禁止 agent 单方调基准）：**
- A. 基线改为滚动中位数（近 14 天 worktree 峰值），只报超出常态的部分；
- B. 该分量设扣分上限（如 ≤20），保底不淹没 orphan/renumber 等真异常信号；
- C. 拆分命名：`worktree_concurrency`（观测）与 `conflict_signals`（告警）分开，
  只有后者进 health 扣分。
任一方案都属指标语义变更，走 ADR；**本 bet 未动任何权重与阈值（redline 遵守）**。

## 4. 交付

- 回归测试：`tests/test_compass_radar_concurrency.py`（hermetic：tmp_path 伪造 runs 目录
  + mock git porcelain，覆盖 active 去重 / 非 active 跳过 / 坏 YAML 跳过 / wt 免费额度）
- 本归因表；retro：`.omo/_knowledge/retros/BET-Y2Q4-T9-01.md`
