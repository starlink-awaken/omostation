---
id: ADR-0312
title: Cockpit Delivery Journey truthful state projection
status: ACCEPTED
date: 2026-08-02
last_updated: 2026-08-02
owner: engineering-team
lifecycle: spec
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/agent-workflow-contract.md
  - ../../../projects/cockpit/src/cockpit/delivery_journey.py
---

# ADR-0312: Cockpit Delivery Journey truthful state projection

## Context

Cockpit 的工程交付旅程需要把 OMO、Agent Workflow 和 Git 事实投影给人类使用者。此前在没有
活动 WorkflowRun 时仍会生成 `git-live-session`，把可读的 worktree 误报为活跃交付；这会让
用户误以为系统正在执行，也无法区分等待、完成、失败和不可用。

## Decision

1. `DeliveryJourney` 继续是只读投影，不创建任务库、运行状态机或业务成功判断。
2. 没有可读取的 WorkflowRun 时，Git worktree 只能提供环境可读性，投影必须返回
   `status=stale`、`mode=waiting_for_run`，并引导用户创建或认领受治理任务。
3. 有真实 Run 时，投影根据 Run 状态返回 `live/active`、`live/completed` 或 `failed/failed`；
   事实源不可读时返回 `unavailable/unavailable`。
4. `scene_binding` 只有在 Run 或其上下文明确携带完整 `scene_id`、`journey_id`、
   `outcome_metric` 时才返回。分支、文件、提交和 worktree 不得推导业务绑定。
5. 产品投影必须提供 `next_action`，让用户知道是继续执行、补绑定、恢复失败、查看证据还是
   开启下一轮复盘；不能用默认绿状态代替动作。

## Consequences

- Cockpit 可以诚实表达“当前没有生产旅程”，并与 `current-state-coherence/v1` 的
  `waiting_for_scenario` 语义对齐。
- 工程 dogfood fixture 仍可覆盖完整链路，但 fixture 的场景绑定必须显式声明，不能代表外部
  业务已经激活。
- 后续真实 J1 运营只需要完善 Run 上下文、证据和结果消费，不需要再建一套产品状态数据库。
- 当前隔离 worktree 中缺失的外部子模块和可选依赖仍属于环境风险，不能被本 ADR 解释为产品失败。

## Verification

- `projects/cockpit` Delivery Journey targeted tests: PASS
- `tests/integration/delivery_journey/test_delivery_journey_e2e.py`: PASS
- `ruff` targeted check: PASS
- `doc-ssot-lint`: PASS
