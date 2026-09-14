---
id: ADR-0359
title: Engineering Delivery Cockpit 人工复核工作台边界
status: ACCEPTED
date: 2026-08-03
owner: governance-team
lifecycle: spec
last-reviewed: 2026-08-03
type: ssot
---

# ADR-0359: Engineering Delivery Cockpit 人工复核工作台边界

## 背景

Phase 65 已在 OMO 中提供工程交付人工复核 broker 和只读 review queue。若 Cockpit 直接读取日志或自行拼接
反馈状态，会形成第二套状态真相；若 UI 直接写 WorkflowRun，也会越过 L3/L2 边界。Phase 66 需要把队列变成可操作的
人类入口，但保持机器摄取、人工复核和 WorkflowRun 生命周期彼此分离。

## 决策

1. Cockpit 在既有 `/api/workflow-mesh` 路由下提供
   `GET /engineering-delivery/review-queue`，只调用 OMO 的 `build_engineering_delivery_review_queue`。
2. Cockpit 提供 `POST /engineering-delivery/review`，仅接受 `workflow_run_id`、`actor_ref`、`delivery_id`、
   `decision`、`reviewed_at` 和 `evidence_refs`，再调用 OMO 的 `record_engineering_delivery_review`。
3. Cockpit 不复制 review 状态机、不直接写 `.omo`、不创建 WorkflowRun、不改变 admission、不派发 worker、不调用 provider。
4. 两个接口固定输出 side-effect controls；队列为 `read_only=true`，人工复核仍由 OMO broker 做最终校验和 append-only 持久化。
5. 队列为空、OMO 不可用或数据不合法时，接口返回结构化 `unavailable`/`invalid`，不以空成功结果掩盖治理依赖缺失。

## 影响

- Cockpit 获得可以直接支撑收件箱和审核表单的稳定 L3 契约。
- OMO 继续拥有交付 receipt、反馈阶段、幂等和安全字段的唯一写入规则。
- UI 后续只需消费 queue projection 并提交有限复核 envelope，不需要理解 OMO 内部日志格式。
- 真实业务样本、双人标注和 adjudication 仍是后续阶段，当前工作台不代表业务价值已验证。

## 验证

```bash
cd projects/cockpit
PYTHONPATH="src:../omo/src" uv run --no-project --with pytest --with fastapi --with httpx pytest -q src/cockpit/tests/test_api_workflow_mesh_operations.py
```
