---
id: ADR-0358
title: Engineering Delivery 机器摄取与人工复核反馈边界
status: ACCEPTED
date: 2026-08-03
owner: governance-team
lifecycle: spec
last_updated: 2026-08-03
---

# ADR-0358: Engineering Delivery 机器摄取与人工复核反馈边界

## 背景

Phase 64 的工程交付消费者已经能够把合并 PR 元数据写入 receipt 和 outcome feedback，但原入口允许调用方传入
`reviewed`/`adopted`，会把机器摄取误标为人工消费，也无法表达持续的人工反馈阶段。后续 Cockpit 需要一个只读运营队列，
但不能为此再造一套 WorkflowRun 或任务状态机。

## 决策

1. `consume-engineering-delivery` 固定只写 `outcome-feedback/v1` 的 `submitted` 状态；机器入口拒绝其它消费状态。
2. 新增 `review-engineering-delivery` broker，要求已有工程交付 receipt、已有 `submitted` feedback、明确 actor、复核时间、决策和至少一条复核证据引用。
3. 人工决策允许 `reviewed`、`adopted`、`rejected`，沿同一 `outcome_id` 追加反馈记录；相同阶段和相同证据幂等，不同阶段不视为冲突。
4. 新增 `engineering-delivery-review-queue/v1` 只读投影，聚合真实 receipt、WorkflowRun 状态、反馈阶段、最新决策、交付时长和证据数量。
5. broker 和投影不得创建/迁移 WorkflowRun、派发 worker、调用 provider、改变 admission 或自动晋升策略。

## 影响

- 系统可以区分“已摄取”“已人工复核”“已采用”“已拒绝”，为真实责任人反馈和后续评测提供可靠标签。
- 正式 UI 可以只消费 review queue，不拥有 WorkflowRun 或 Outcome 的第二套状态真相。
- 历史 Phase 64 数据若含旧的 `reviewed` 记录仍可读取；新数据不会继续制造该语义混淆。

## 验证

```bash
cd projects/omo
PYTHONPATH=src uv run --no-project --with pytest --with pyyaml --with pydantic pytest tests/test_engineering_delivery_consumer.py -q
PYTHONPATH=src uv run --no-project --with ruff ruff check src/omo/engineering_delivery_consumer.py src/omo/omo_external_resources.py tests/test_engineering_delivery_consumer.py
```
