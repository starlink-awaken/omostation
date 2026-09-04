---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-28
bet_id: BET-Y1Q3-T4-05
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Product P0 WP2 — Honest Agent Cell Effect Receipt

## 1. 目标

消除 Agent Cell `Executor` 中“没有执行却返回成功”的固定分支。任何 effectful action 只有在消费已准入 workflow context、通过已有 canonical effect adapter 真实执行，并持久化 durable receipt 后才能返回 `ok: true`。

本 WorkPacket 依赖 WP4：任何 effectful execution 在到达 Executor 前必须已绑定 principal authority。

## 2. 当前反例

`projects/omo/src/omo/resident/executor.py` 对 `generate_doc`、`create_draft`、`format_code`、`run_tests`、`backup` 和 `snapshot` 直接返回伪造成功信息。`execute_plan()` 再根据这些固定 `ok` 聚合 `completed=true`。该路径没有 admission identity、effect journal、持久回执或重放保证。

## 3. 设计原则

- 保留 `read_file`、`list_files`、`search`、`query_status` 等真实只读操作。
- 从 local backend 移除所有 fixed-success effectful 分支。
- 不创建第二 effect adapter 或 receipt store；复用 `projects/omo/src/omo/sandbox_tool_runner.py` 和已有 Workflow Mesh/Event Ledger authority。
- 只支持已有 adapter 能可确定执行的最小操作；其他 action 明确返回 `effect=not_executed`。
- 拒绝发生在文件、subprocess、provider、tool 或 ledger effect 之前。

## 4. 输入与输出合同

Effectful task 必须携带下列已持久身份：

- `workflow_run_id`
- `trace_id`
- `dispatch_id`
- `worker_id`
- `step_run_id`
- `admission_id`
- `packet_id` / `packet_hash`
- `principal_authority_ref` / `principal_receipt_digest`
- `input_ref` / `input_digest`

成功结果：

```python
{
    "ok": True,
    "effect": "executed",
    "receipt_schema": "sandbox-tool-receipt/v1",
    "receipt_event_id": "event:...",
    "idempotency_key": "...",
}
```

未准入或不支持结果：

```python
{
    "ok": False,
    "effect": "not_executed",
    "error": "admitted workflow context required for effectful action: <action>",
}
```

`execute_plan.completed` 只能由每个 task 的真实 receipt-backed 结果推导。

## 5. 写面

- `projects/omo/src/omo/resident/executor.py`
- `projects/omo/tests/test_resident_executor_truth.py`
- `projects/omo/tests/test_age_v2_realworld.py`

`sandbox_tool_runner.py` 只作为已有权威读面；如果必须修正其 contract，先停机并对 Spec 做书面修订，不在实施中默认扩大写面。

## 6. 负例和重放

- 无 admitted context：拒绝，目标文件不存在，事件计数不变。
- forged admission/worker/step/principal digest：拒绝，provider/tool/runtime/ledger effect 为零。
- 回执持久失败：不得返回 success。
- 相同 idempotency identity 重试：复用原 receipt，不再执行效果。
- 相同 identity 但 input digest 不同：拒绝 replay conflict。

## 7. 验收和验证

1. RED 证明现有 `generate_doc` 在无 admitted context 时错误返回 success。
2. 修正后所有 fixed-success action 都是 receipt-backed 或明确 unavailable。
3. 一个临时目录中的可确定效果真实执行，产生 durable receipt，进程重启后可重放。
4. 相同请求重试不产生第二份 receipt 或第二次 effect。
5. 负例对目标文件、subprocess、provider、tool 和 ledger 事件均为零副作用。

```bash
cd projects/omo
uv run pytest tests/test_resident_executor_truth.py tests/test_age_v2_realworld.py tests/test_sandbox_tool_runner.py -q
```

## 8. 回滚与停机

回滚时关闭 resident effect route，保留真实只读操作和已持久 receipt；不得恢复 fixed success。任一成功无 durable receipt、任一拒绝有副作用或 principal binding 不一致时立即停机。

## 9. 价值政策

`value_indicator_policy=false`。effect receipt 证明工程执行，不证明个人采纳或价值。
