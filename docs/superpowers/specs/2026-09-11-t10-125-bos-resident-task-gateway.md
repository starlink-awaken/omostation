---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y1Q4-T10-125 specification
bet_id: BET-Y1Q4-T10-125
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-11
---


# BET-Y1Q4-T10-125: Resident BOS 双向任务网关与异步队列调度中枢

## Status

accepted

## Context

常驻 Agent 体系 (omo-resident, ADR-0396) 已有 4 个 BOS 端点（status/roles/daemon/decision）覆盖只读状态与单次执行。

但常驻 agent 缺乏"提交异步任务"的对称入口：外部触发者（人或 agent）无法把"分析 X 文档 / 巡检 Y 服务 / 对账 Z 数据"这类长时任务投递到常驻 daemon 的就绪队列、由 daemon 在周期 tick 中拉取执行并把产物落盘。

需要在 BOS 端、roter 规则端、daemon tick 端三处贯通：
- 4 个新 BOS URI（task/submit, task/status, sediment/trigger, decision/trigger）
- 持久化任务队列（不引入 Redis/SQLite 之外的外部依赖）
- daemon tick 拉取就绪任务并落地执行结果

## Goals

- 4 个新 BOS 端点 + 端到端任务生命周期（submit → queued → running → completed/failed）
- 常驻 daemon 在每次 tick 中扫描就绪队列、派发到 handler、持久化状态机
- 队列最大长度保护（默认 1000），溢出拒绝入队并降级告警
- 单元测试 + CI 门禁通过

## Non-Goals

- 不引入外部 Redis 或消息中间件
- 不修改现有 4 个只读 URI 契约
- 不改造 daemon 主循环（仅在 tick_once 中加入新 hook）

## Architecture

```
External Trigger
    ↓
BOS dispatch (bos://resident/task/submit)
    ↓
projects.omo.resident.task_queue.submit()
    ↓
SQLite table: resident_tasks (id, status, payload, attempts, created_at)
    ↓
daemon.tick_once() → pull queued → execute → status: completed/failed
    ↓
BOS dispatch (bos://resident/task/status) returns latest
```

## Endpoints (新增 4 个)

| URI | action | 描述 |
|---|---|---|
| `bos://resident/task/submit` | task_submit | 入队任务，返回 task_id |
| `bos://resident/task/status` | task_status | 查任务状态（queued/running/completed/failed）|
| `bos://resident/sediment/trigger` | sediment_trigger | 触发 sediment 写入（异步）|
| `bos://resident/decision/trigger` | decision_trigger | 触发 decision 提案 |

## Constraints

- 队列默认 max=1000，溢出拒绝（不阻塞外部）
- 任务 status 状态机：queued → running → completed/failed，禁止反向
- 失败重试上限：3 次（attempt 字段追踪）
- 不阻塞 BOS 主线程：submit 返回 task_id 即可，执行异步

## Criteria

- [ ] bos-services.yaml 登记 4 个新 URI 并通过 check-resident-bos.py
- [ ] check-resident-bos.py REQUIRED_URIS 扩展到 8 个
- [ ] task_queue.py 实现 submit/poll/complete/fail 状态机
- [ ] daemon.py tick_once 增加 _process_task_queue hook
- [ ] tests/unit/test_resident_task_queue.py 覆盖 4 个 URI + 状态机
- [ ] pytest exit 0
- [ ] make gac-local-gate exit 0

## Test Strategy

- 单元测试：submit/poll/complete/fail 各 5+ case，覆盖正常路径、溢出、并发、重试
- 集成测试：mock BOS dispatch → 验证 URI 与 daemon 集成
- 回归测试：现有 4 个 URI 不能坏
- CI：check-resident-bos.py 必检 8 条 URI

## Phase 1 Deliverables

1. `projects/agora/etc/bos-services.yaml` 新增 4 个 resident 端点
2. `bin/gac/check-resident-bos.py` REQUIRED_URIS 扩展至 8 条
3. `projects/omo/src/omo/resident/task_queue.py` SQLite-backed 状态机（~150 LOC）
4. `projects/omo/src/omo/resident/daemon.py` tick_once 增加 _process_task_queue hook
5. `projects/omo/tests/unit/test_resident_task_queue.py` 覆盖完整状态机
6. `.omo/_knowledge/retros/BET-Y1Q4-T10-125.md` retro

## Dependencies

- `BET-Y1Q4-T10-05` ✅ done (提供离线沙箱金库最小闭环，本 BET 复用其 BOS 接入)
