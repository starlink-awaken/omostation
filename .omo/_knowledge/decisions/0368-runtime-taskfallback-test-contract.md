---
id: ADR-0368
title: Runtime Registry 测试契约与 TaskFallback 响应对齐
status: ACCEPTED
date: 2026-08-04
owner: governance-team
lifecycle: spec
last-reviewed: 2026-08-04
related:
  - 0366-pyright-sweep-algorithm.md
  - 0367-sweep-tooling-scaling-roadmap.md
type: ssot
---

# ADR-0368: Runtime Registry 测试契约与 TaskFallback 响应对齐

## 背景

PR #940 合并了 `bin/sweep` 工具链与 `pyright-sweep` workflow。清理过程中发现
`projects/runtime/tests/test_registry.py` 的两个测试与 `TaskFallbackManager` 的
实际响应契约不一致，导致偶发失败（flaky）：

- `test_submit_no_agent` 断言 `POST /tasks` 返回 `status == "pending"`，
  但 `submit_task` 经 `TaskFallbackManager.submit_with_fallback()` 后，无可用
  agent 时在 `max_retries+1` 次尝试后返回 `ESCALATED`，HTTP 响应为
  `status: "escalated", attempts: 4`。
- `test_failover_redispatches_inflight_task` 直接读取 `POST /tasks` 响应里的
  `agent_id` 字段，但该响应只包含 `task_id / status / attempts / error`；
  任务分配信息只能通过 `GET /tasks` 的 assignment 列表读取。

## 决策

1. `test_submit_no_agent` 断言改为 `status == "escalated"` 且 `attempts == 4`
   （`max_retries=3` 时 1 次立即尝试 + 3 次重试），对齐
   `TaskFallbackManager` 的 ESCALATED 语义。
2. `test_failover_redispatches_inflight_task` 改为：先断言
   `POST /tasks` 返回 `status == "dispatched"`，再从 `GET /tasks` 的
   assignment 列表取 `agent_id` 断言归属，对齐
   `Dispatcher.get_assignments()` 的返回面。
3. 两个测试都不再依赖 `TaskFallbackEvent` 未暴露给 HTTP 的内部字段，
   避免测试与实现耦合漂移再次发生。

## 影响

- 测试与实现契约对齐后，`uv run --project projects/runtime pytest tests/test_registry.py -q`
  稳定通过（35/35），连续 10 轮无 flake。
- `test_registry.py` 的响应断言成为 `submit_task` 响应面的回归守门。

## 验证

```bash
uv run --project projects/runtime pytest projects/runtime/tests/test_registry.py -q
# 期望: 35 passed

uv run --project projects/runtime ruff check projects/runtime/tests/test_registry.py
# 期望: All checks passed
```
