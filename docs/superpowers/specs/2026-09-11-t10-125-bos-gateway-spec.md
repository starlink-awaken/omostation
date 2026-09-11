---
schema_version: specification/v1
spec_version: 1.0.0
title: Resident BOS 双向任务网关与异步队列调度中枢
bet_id: BET-Y1Q4-T10-125
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-11
last-reviewed: 2026-09-11
risk_level: L2
human_gate: false
type: ssot
last_updated: 2026-09-11
decision_ref: decision://accepted/BET-Y1Q4-T10-125
---

# Resident BOS 双向任务网关与异步队列调度中枢（BET-Y1Q4-T10-125）

## 背景（Context）

resident 常驻体系目前的事件驱动是单向订阅（`resident-routes.yaml` 规则 → daemon tick 消费），
缺少"外部请求 → 常驻内核执行 → 状态回报"的双向任务通道，也没有持久化的任务就绪队列。
外部/上游 agent 无法可靠地向 resident 提交一次性任务并轮询其完成状态。

本 spec 为 BET-Y1Q4-T10-125 建立契约：以 ledger `goal/done_when/verify` 为准，
在 BOS 服务登记与 resident 路由中扩展 4 个双向任务端点，
并在常驻内核中构建持久化任务就绪队列（SQLite + 本地原子事务，不引入外部中间件），
守护进程每次 tick 拉取就绪任务执行并持久化状态机。

## 目标（Goal）

在 `bos-services.yaml` 与 `resident-routes.yaml` 中扩展双向任务端点：

- `bos://resident/task/submit` — 提交任务入队（返回 task_id）
- `bos://resident/task/status` — 查询任务状态（pending/running/done/failed）
- `bos://resident/sediment/trigger` — 触发知识沉淀任务
- `bos://resident/decision/trigger` — 触发决策提案任务

在常驻内核中构建持久化任务就绪队列（`projects/omo/src/omo/resident/task_queue.py`），
支持 `submit/poll/complete/fail` 状态机（queued → running → completed | failed），
守护进程在每次 tick 时拉取就绪任务并持久化状态机。

## 非目标（Non-Goals）

- 不引入外部 Redis 或消息中间件，依托本地原子事务文件与 SQLite 实现。
- 不修改现有只读状态服务的 URI 契约（`bos://resident/core/status`、`bos://resident/core/roles` 等不变）。
- 不做任务重试/死信/分布式语义，本 bet 只做单机本地闭环的持久化队列。
- 不修改其他 BET、completion/value evidence、branch protection 或业务运行态。

## 完成标准（Done When）

1. `bos-services.yaml` 登记 4 个双向任务端点并通过 `check-resident-bos.py` 校验。
2. 交付 `projects/omo/src/omo/resident/task_queue.py`，支持 `submit/poll/complete/fail` 状态机
   与队列最大长度上限保护（默认 1000，溢出拒绝入队并降级告警）。
3. `resident-orchestrator-daemon` 支持在周期 tick 中拉取并执行就绪任务。
4. 单元测试 `projects/omo/tests/unit/test_resident_task_queue.py` 通过（状态机 + 上限 + 持久化）。
5. `make gac-local-gate` 与默认 workflow verify/compliance 通过。

## 验证（Verify）

- `uv run pytest projects/omo/tests/unit/test_resident_task_queue.py -q` → exit 0。
- `python3 bin/gac/check-resident-bos.py` → exit 0。
- `make gac-local-gate` → exit 0。
- `uv run --with pyyaml python bin/agent-workflow.py compliance` → 通过（run/lock/ledger/evidence 合规）。

## 落地备注（Implementation Notes）

- 队列内核与 daemon tick hook 已随 omo 子模块基线交付（`task_queue.py` + `_process_task_queue`），
  本 spec 首批闭环聚焦契约侧：spec 定稿 + ledger binding + 端点登记与校验接线。
- 4 个新端点的 `bos-services.yaml` 登记（agora 子模块）与 `check-resident-bos.py` 期望 URI 扩展，
  按 `write_surfaces` 分批 claim 实施，不在本批次一次性合入。
