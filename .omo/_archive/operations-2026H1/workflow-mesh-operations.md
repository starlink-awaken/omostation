---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: Workflow Mesh 运营投影与复盘队列
type: doc
---
# Workflow Mesh 运营投影与复盘队列

## 目的

Workflow Mesh 的运行事件、证据和恢复记录已经能够重建单条 `WorkflowRun`。本阶段补齐面向
J1 连续运营的只读聚合视图：让人看到运行规模、交付里程碑、异常恢复队列和场景归因，同时
明确哪些业务结果仍然未知。

唯一事实源仍是 OMO 的 append-only 事件日志：
`_knowledge/workflow-mesh/events.jsonl`。运营投影不写事件、不创建任务、不改变运行状态，也
不复制一份 Cockpit 私有统计库。

## 契约

OMO 函数 `build_operations_snapshot()` 输出 `workflow-mesh-operations/v1`。Cockpit 通过
`GET /api/workflow-mesh/operations` 暴露同一投影，`scene_id` 参数只做读取过滤。

顶层字段：

| 字段 | 含义 |
| --- | --- |
| `summary` | 运行数、里程碑数、状态分布、时长和可解释比率 |
| `by_scene` | 按完整 `scene_binding` 聚合；无绑定统一归入 `_unbound` |
| `review_queue` | 根据当前状态生成建议动作，不创建新任务 |
| `consumption` | 业务消费观测状态、可反馈结果和显式回执；没有显式回执时必须是 `not_observed` |

### 指标语义

- `succeeded_runs` 由 `WorkflowSucceeded` 事件判定，不等于验证或业务价值实现。
- `verified_runs` 由 `WorkflowVerified` 事件判定，要求已有 `EvidenceRecorded`。
- `closed_runs` 由 `WorkflowClosed` 事件判定，只表示运行生命周期收口。
- `failed_runs` 和 `unavailable_runs` 统计运行历史上出现过的对应事件；恢复后的运行仍保留
  故障事实，避免用当前绿状态抹平可靠性问题。
- `rates` 只在分母存在时计算；没有样本返回 `null`，不返回伪造的 0%。
- `average_duration_seconds` 只使用事件时间戳完整的运行；没有可计算样本返回 `null`。
- `consumption.status` 只有三种语义：`not_observed` 表示尚无显式回执，`observed` 表示至少
  一条非拒绝反馈，`rejected` 表示已有反馈但目前全部是拒绝。关闭、验证、证据存在和 PR
  合并都不能推断用户已经阅读、采用或完成业务回写。
- `eligible_outcomes` 列出带完整场景绑定且已进入 `succeeded/verified/merged/closed` 的结果，
  供人工反馈表单选择；它不是业务成功断言。
- `feedback` 只暴露安全引用、状态、指标摘要和时间，不暴露备注原文、提示词、模型输出或凭据。

## 复盘队列

队列是确定性的只读建议：

| 状态 | 分类 | 建议动作 |
| --- | --- | --- |
| `waiting_approval` | approval | `approval` |
| `failed` / `unavailable` | recovery | 恢复运行、恢复后端或接管租约 |
| `succeeded` | verification | 用证据完成验证 |
| `verified` | delivery | 合并或关闭交付 |
| `merged` | closeout | 关闭运行 |
| `closed` 且无场景绑定 | attribution | 补齐场景归因用于复盘（优先于证据提示） |
| `closed` 且有场景绑定、无证据 | evidence | 复核证据完整性 |

这些建议不替代 OMO admission，也不通过 Cockpit 直接执行。执行动作仍必须回到既有的受治理
任务、WorkflowRun 和证据链。

## 结果消费反馈

结果消费使用独立的 `outcome-feedback/v1` 追加日志，详见
[`outcome-feedback.md`](./outcome-feedback.md)。反馈不改变 `WorkflowRun` 状态，也不新增
`OutcomeConsumed` 运行事件：WorkflowRun 仍是执行生命周期真相，反馈日志是价值消费证据面。
Cockpit 提供 `POST /api/workflow-mesh/outcome-feedback` 和“运营闭环”页面；OMO 负责场景绑定、
结果资格、隐私字段和幂等校验。

## 下一步边界

当前不新增 `OutcomeConsumed` 运行态事件。反馈只记录明确观察到的消费行为；它不会自动激活外部
资源、派发业务任务或替代 Scene Card 审批。这样可以避免把“工程完成”误报成“业务有效”，也
避免在没有真实场景时建设第二套结果数据库。

外部知识、数据、资料、方法和工具的连接仍遵守 External Connection Fabric 与 Scene Card
激活门：资源可以被发现和候选化，但没有真实业务场景、权限、消费者、结果指标和回滚证据时，
只能保持 `proposal_only` 或 `sandbox`。

## 验证

```bash
cd projects/omo
PYTHONPATH=src uv run --no-project --with pytest --with pyyaml --with pydantic --with httpx python -m pytest -q tests/test_workflow_operations.py tests/test_workflow_eval.py

cd ../cockpit
PYTHONPATH=src uv run --no-project --with pytest --with fastapi --with httpx --with pyyaml --with rich python -m pytest -q src/cockpit/tests/test_api_workflow_mesh_operations.py

cd ../cockpit-ui
bun run test:unit -- src/components/__tests__/WorkflowMeshOperationsView.test.tsx
bun run build
```
