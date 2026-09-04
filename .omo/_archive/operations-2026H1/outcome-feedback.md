---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: Workflow Mesh 结果消费反馈
type: doc
---
# Workflow Mesh 结果消费反馈

## 目的

`WorkflowRun` 的 `verified`、`merged` 和 `closed` 只能证明工程生命周期，不证明结果已经被人
或业务系统消费。结果消费反馈是独立的证据面，用来记录“谁在什么时候以什么方式看到了哪个
结果，以及是否形成了可引用的结果”。它不改变 WorkflowRun 状态。

## 契约

- schema：`outcome-feedback/v1`
- 持久化：OMO `_knowledge/workflow-mesh/outcome-feedback.jsonl`
- API：`POST /api/workflow-mesh/outcome-feedback`
- 运营投影：`GET /api/workflow-mesh/operations`
- UI：Cockpit `/workflow-mesh-operations`

允许的 `consumption_state`：`reviewed`、`adopted`、`submitted`、`dispatched`、`cited`、
`rejected`。

必填字段：

| 字段 | 约束 |
| --- | --- |
| `workflow_run_id` | 必须指向已存在且已形成结果的 WorkflowRun |
| `outcome_id` | 结果引用；当前 UI 使用 `outcome:<workflow_run_id>` |
| `scene_binding` | 必须完整包含 `scene_id`、`journey_id`、`outcome_metric`，且和 WorkflowRun 完全一致 |
| `consumption_state` | 只能使用允许的状态 |
| `consumer_ref` | 脱敏的消费者引用，不放个人隐私或凭据 |

可选字段包括 `result_ref`、`evidence_refs`、结构化 `value`、`observed_at` 和 `note`。`value`
只允许 `amount`、`unit`、`baseline`、`comparison`；备注原文不落盘，仅保存 `note_digest`。
常见密码、token、私钥、原始输入/输出和原始内容字段在递归校验中一律拒绝。

## 资格与幂等

只有状态为 `succeeded`、`verified`、`merged` 或 `closed`，并且场景绑定匹配的 WorkflowRun
才能写反馈。反馈使用核心字段生成稳定 idempotency key；重复提交返回 `deduplicated`，不会
追加第二条相同回执。反馈日志采用 OMO append-only log 和文件锁，读取时逐条校验契约。

## 投影语义

`consumption.status` 的含义严格固定：

- `not_observed`：还没有任何显式反馈；不能解释为失败，也不能解释为成功。
- `observed`：至少存在一条非 `rejected` 反馈。
- `rejected`：已有反馈，但当前全部为 `rejected`。

`eligible_outcomes` 只是可填写反馈的结果候选，不是业务价值结论。`consumption_rate_among_eligible_closed_runs`
只对带证据的 `closed` 运行计算，分母为零时返回 `null`。

## 边界

反馈不是 `OutcomeConsumed` 运行事件，不驱动状态迁移，不直接触发外部连接、OMO 任务派发或
模型学习。外部知识、数据、方法、工具和渠道仍必须通过 External Connection Fabric、Scene
Card、admission、receipt 和权限边界；没有真实业务消费者和责任人时保持 proposal-only 或
sandbox。

## 验证

```bash
cd projects/omo
PYTHONPATH=src uv run --no-project --with pytest --with pyyaml --with pydantic --with httpx python -m pytest -q tests/test_outcome_feedback.py tests/test_workflow_operations.py tests/test_workflow_eval.py tests/test_workflow_mesh.py

cd ../cockpit
PYTHONPATH=src uv run --no-project --with pytest --with fastapi --with httpx --with pyyaml --with rich python -m pytest -q src/cockpit/tests/test_api_workflow_mesh_operations.py

cd ../cockpit-ui
bun run test:unit -- src/components/__tests__/WorkflowMeshOperationsView.test.tsx
```
