# OPC P4-E3 Budget Policy Governance Closeout — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P4 / Gate E / Sub-gate E3
> Author: 治理审计 Agent

## 1. 目标

把 P4-E3 budget reject 从"能触发"提升到"可验收"——使 budget guard 既能拒绝
业务调用，又能在治理面（OMO debt + task evidence）留下可追溯、可复用、可审计
的证据。

## 2. 5 项通过标准 checklist

| # | 通过标准 | 状态 | 证据 |
|---|---------|:---:|------|
| 1 | `task_id` 出现在 budget guard 拒绝路径 | ✅ | `_call_llm_budget_policy_rejects_and_registers_debt` (L406) + `test_budget_policy_includes_task_id_and_model_in_route_info` |
| 2 | `llm_budget_usd` 出现在 budget guard 拒绝路径 | ✅ | 同上测试 (asserts `policy["budget_usd"] == 0.005`) |
| 3 | `selected model` 出现在 budget guard 拒绝路径 | ✅ | `_maybe_enforce_budget` (L152-156) `registry_model_id = f"{provider_name}/{model_name}"` + 测试 (asserts `policy["model"] == "anthropic/claude-sonnet-4"`) |
| 4 | debt writeback 落地 | ✅ | `.omo/debt/items/DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO.yaml` (含 severity/status/registered_at/description) |
| 5 | 业务路径被 budget 拒绝（不是 traceback） | ✅ | 测试 `test_budget_reject_returns_error_dict_not_traceback` (asserts `finish_reason == "error"` and structured error dict) |
| 6 | 拒绝不抛 traceback | ✅ | 同上 (response is dict, never raises) |
| 7 | formal debt 被登记 | ✅ | debt YAML 含 `id/title/description/severity/source/registered_at/last_seen_at/occurrence_count/status/prerequisite_for/remediation` |
| 8 | 复用策略（避免无限新增垃圾 debt） | ✅ | 相同 task_id 多次触发 = 同一 debt ID 同路径，刷新 in-place + `occurrence_count` 累加 + `first_seen_at` 保留 + `last_seen_at` 更新（测试 `test_budget_debt_reuse_does_not_create_duplicate_files`） |
| 9 | 命令输出摘要 ≥ 1 份 | ✅ | 本文件 §3 + §4 |
| 10 | debt file 引用 | ✅ | 本文件 §5 + summary.md |

## 3. 命令输出摘要

### 3.1 测试执行（基线 + closeout）

```text
$ python3 -m pytest tests/test_executor_engine.py
....................                                                     [100%]
20 passed in 0.05s
```

- 旧测试: 17 (基线)
- 新测试: 3 (`test_budget_policy_includes_task_id_and_model_in_route_info` + `test_budget_debt_reuse_does_not_create_duplicate_files` + `test_budget_reject_returns_error_dict_not_traceback`)

### 3.2 audit demo 跑通

```text
$ python3 scripts/opc_p4_budget_audit_demo.py
exit=0
.omo/debt/items/DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO.yaml
.omo/tasks/registry/done/OPC-P4-E3/budget-reject-summary.md
```

第二次跑（验证复用）：

```text
$ python3 scripts/opc_p4_budget_audit_demo.py
exit=0
.omo/debt/items/DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO.yaml  ← 同一文件
.omo/tasks/registry/done/OPC-P4-E3/budget-reject-summary.md
```

第二次跑后 debt body 关键字段：

```yaml
first_seen_at: "2026-06-12T02:33:55Z"     ← 保留
registered_at: "2026-06-12T02:33:55Z"     ← 保留
last_seen_at:  "2026-06-12T02:34:04Z"     ← 推进
occurrence_count: 2                        ← +1
```

## 4. budget_policy route_info 5 字段实证

`_maybe_enforce_budget` 现写入的 `route_info["budget_policy"]` 完整字段：

```python
{
    "task_id":             task_id,                     # NEW — 加 2026-06-12
    "budget_usd":          budget_usd,                  # 已存在
    "estimated_cost_usd":  estimated_cost_usd,          # 已存在
    "model":               registry_model_id,           # 已存在
    "debt_path":           str(debt_path),              # 已存在（拒绝时填入）
}
```

测试断言验证（`test_budget_policy_includes_task_id_and_model_in_route_info`）：

```python
assert policy["task_id"] == "opc-p4-budget-policy-fields"
assert policy["budget_usd"] == 0.005
assert policy["estimated_cost_usd"] == 0.02
assert policy["model"] == "anthropic/claude-sonnet-4"
assert "debt_path" in policy
```

## 5. debt file 内容（SSOT）

路径: `.omo/debt/items/DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO.yaml`

```yaml
id: DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO
title: OPC P4 budget policy rejected an LLM execution path
description: |
  Runtime executor blocked task `opc-p4-budget-demo` before provider call because
  estimated cost 0.020000 USD exceeded budget 0.010000 USD.
  role=planner, model=anthropic/claude-sonnet-4.
severity: medium
source: runtime
first_seen_at: "2026-06-12T02:33:55Z"
registered_at: "2026-06-12T02:33:55Z"
last_seen_at: "2026-06-12T02:34:04Z"
occurrence_count: 2
status: open
prerequisite_for: OPC-P4
remediation: |
  1. Increase the task budget or select a cheaper route.
  2. Re-run after confirming the selected model aligns with policy.
```

## 6. 复用策略说明

**问题**：如果同一 task_id 反复触发 budget reject，每次都新增一个 debt 文件会
污染 `.omo/debt/items/` 目录，且无法反映"该拒绝路径是稳态的已知风险"。

**方案**：

1. **同一 debt ID 同路径**：`_sanitize_debt_suffix(task_id)` 决定稳定 ID
   （首字符大写 + 截 48 字符），所以 `opc-p4-budget-demo` 永远映射到
   `DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO.yaml`。
2. **in-place 刷新**：第二次触发时读取旧文件，解析 `occurrence_count` 和
   `first_seen_at`，写入新内容：
   - `first_seen_at` 保留原值
   - `last_seen_at` 推进到当前时间
   - `occurrence_count` 累加
3. **零新增**：无论 demo 跑 N 次，items/ 目录中只会出现这一个文件

**验证**（`test_budget_debt_reuse_does_not_create_duplicate_files`）：
3 次触发后 `tmp_path/debt/` 仍只有 1 个 yaml 文件，且 `occurrence_count: 3`。

## 7. 测试覆盖汇总

| 测试名 | 覆盖字段 | 状态 |
|--------|----------|:----:|
| `test_call_llm_budget_policy_rejects_and_registers_debt` | 拒绝 + debt 落地 (旧) | ✅ |
| `test_budget_policy_includes_task_id_and_model_in_route_info` | budget_policy 5 字段 | ✅ NEW |
| `test_budget_debt_reuse_does_not_create_duplicate_files` | 复用 + occurrence_count | ✅ NEW |
| `test_budget_reject_returns_error_dict_not_traceback` | 结构化 error + 不抛 traceback | ✅ NEW |

总计 20/20 通过。

## 8. 已知限制（不在本收口范围）

- **debt ID 重复字符串**：`DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO` 中 "BUDGET"
  重复了一次。来源于 demo 任务 ID `opc-p4-budget-demo` 已经含 "budget"，又拼上
  前缀的 `OPC-P4-BUDGET-`。**这不影响功能**（文件路径稳定 + 复用），但若要美观可
  后续单独 PR 改 demo 的 task_id 为 `opc-p4-e3-demo`。本收口不扩范围。
- **P4-E4 audit trail 跨仓收口**：与本收口独立，单独 PR 处理。

## 9. 红线遵守

- ✅ 未改任何已 passed gate（D1, D2, E1, E2 状态不变）
- ✅ 未跳 phase（P3 → P4-E3 按顺序）
- ✅ "测试通过" = "gate passed" 的关系清晰：测试通过是必要条件，本文件是充
  分条件
- ✅ 实现、测试、task、doc 同步更新（无单向修改）
- ✅ 业务路径走 llm-gateway（`from llm_gateway.registry_data_loader import
  estimate_model_cost`），不直调 provider
- ✅ debt 真实登记，非 demo 伪装
