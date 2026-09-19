---
schema_version: specification/v1
spec_version: 1.0.0
title: 合同网协议 (CNP) 任务自主竞标与临时突击队动态自组织编排设计
bet_id: BET-Y1Q4-T7-06
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
value_indicator_policy: false
---

# T7-06 — Contract Net Protocol & TaskForce 编排设计

## 1. 问题

多 Agent 并发执行时, 任务指派是中心化的（静态路由）, 无资质的 agent
可能被盲派, 任务无人认领时无限期空转, 临时协同没有"组队-解散"生命周期。

## 2. 非目标（与 ledger non_goals 一致）

- 不允许无技能资质的 Agent 盲目投标（资质门槛硬性）。
- 不在无超时兜底的情况下无限期等待投标。

## 3. 设计（确定性算法, 零模型调用）

### 3.1 竞标状态机与评分（`projects/omo/src/omo/resident/contract_net.py`）

- `TaskAnnouncement`: task_id / required_skills / bid_window_s / payload。
- `Bid`: agent_id / skills / token_cost(评估消耗) / confidence /
  estimated_duration_s。
- **资质门槛**: agent skills 必须覆盖全部 required_skills, 否则 bid
  被 `not_eligible` 拒绝（不进入评分）。
- **评分**: `score = 2.0·skill覆盖率 + 1.5·confidence + 1.0·(1/(1+duration))
  − 0.5·token_norm`, 纯确定性计算。
- **Token 预算（circuit breaker）**: 评估消耗累计 > 500 token → 强制截断,
  转默认 Archetype 兜底指派。
- **超时兜底**: bid_window 默认 3s; 窗口内无合格中标者（或被截断）→
  `Fallback(task_id, archetype_default)`——超时兜底率 100%（测试对
  多场景断言）。
- `evaluate(announcement, bids, elapsed_s)` 纯函数; 单次评估为纯内存
  计算, 测试实测 ≤300ms。

### 3.2 临时突击队编排（`projects/omo/src/omo/resident/taskforce.py`）

- `TaskForce`: force_id / task_id / leader(中标者) / members(合格投标人
  择优) / created_at / ttl_s / status(active|disbanded) / disband_reason。
- `TaskForceManager`: `create(award, bids)`（leader = award.agent_id,
  members 按评分择优上限 5）, `disband(force_id, reason)`,
  `active()`, `sweep_expired()`（ttl 过期自动解散）; 解散幂等。

### 3.3 测试（`projects/omo/tests/test_contract_net.py`）

资质门槛拒绝 / 评分确定性与最优覆盖 / Token 截断兜底 / 3s 超时兜底率
100%（多场景）/ 评估耗时 ≤300ms（perf 实测）/ TaskForce 生命周期与过期清扫。

## 4. 完成判据映射

| done_when | 落点 |
|---|---|
| contract_net.py 竞标状态机与评分算法 | §3.1 |
| taskforce.py 临时突击队编排管理 | §3.2 |
| 评估 ≤300ms / Token ≤500 / 3s 超时兜底率 100% | §3.1 + §3.3 实测断言 |

## 5. 风险与回滚

纯新增模块（零依赖, 零网络）+ ledger 条目; 回滚 = revert 单 PR。
