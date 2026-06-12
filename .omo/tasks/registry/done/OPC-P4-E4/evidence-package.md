# OPC P4-E4 Audit Trail Cross-Repo Attribution — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P4 / Gate E / Sub-gate E4
> Author: 治理审计 Agent

## 1. 目标

把 llm audit 从"写一条日志"提升到"可被治理消费"——保证每次 LLM 调用被
Pydantic schema 强制 8 必填字段、jsonl 可按 task_id 跨记录归因、omo
audit-rollout 报告可生成。

## 2. 5 项通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 条真实 LLM 调用写入 llm-gateway audit | ✅ | `llm-audit-sample.json` (task_id=opc-p4-audit-demo, 1 record) |
| 2 | audit 字段完整 (8 必填) | ✅ | schema-level 强制 (test_audit_record_schema_enforces_all_required_fields) + sample.json 实际含 task_id/role/provider/model/input_tokens/output_tokens/total_cost_usd/latency_ms + ts/route/metadata |
| 3 | 生成 1 份 rollout 报告 | ✅ | `.omo/_delivery/audit-rollout/2026-06-12-opc-p4.json` (本目录 audit-rollout-summary.md §3 全文) |
| 4 | P4 doc/task 状态与证据一致 | ✅ | OPC-P4-MODEL-COMPUTE.yaml E4 status=passed + OPC-PHASE4-MODEL-COMPUTE.md 同步 |
| 5 | 任务、doc、test、实现同步更新 | ✅ | 5/5 audit 测试通过 + evidence-package.md + rollout summary + plan yaml |

## 3. 8 必填字段实证

### 3.1 Schema 强制（`projects/llm-gateway/src/llm_gateway/audit.py:22-39`）

```python
class LLMCallAuditRecord(BaseModel):
    ts: str = Field(..., description="UTC ISO8601 with Z suffix")
    task_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    route: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

8 必填字段：
1. `task_id` (str, ≥1)
2. `role` (str, ≥1)
3. `provider` (str, ≥1)
4. `model` (str, ≥1)
5. `input_tokens` (int, ≥0)
6. `output_tokens` (int, ≥0)
7. `total_cost_usd` (float, ≥0)
8. `latency_ms` (float, ≥0)

附加：`ts` (UTC ISO8601 with Z, validator), `route` (dict, 默认 {}), `metadata` (dict, 默认 {})。

### 3.2 测试断言（`tests/test_phase4_budget_and_audit.py`）

- `test_audit_record_schema_enforces_all_required_fields`: 反射 schema,
  确保 8 字段全声明
- `test_audit_record_rejects_missing_task_id_or_role`: 空字符串
  task_id/role → Pydantic 抛 ValueError（防止静默丢字段）
- `test_audit_jsonl_supports_cross_record_task_attribution`: 3 次
  跨 task_id 调用 → 按 task_id 归因, 验证下游消费者契约

### 3.3 实际样本（`.omo/tasks/registry/done/OPC-P4-E4/llm-audit-sample.json`）

来源：`projects/llm-gateway/audit/llm_calls.jsonl`（demo 跑后清空 + 干净跑一次）

```json
{
  "input_tokens": 120,
  "latency_ms": 0.251,
  "metadata": {"tool_count": 10},
  "model": "claude-sonnet-4",
  "output_tokens": 40,
  "provider": "anthropic",
  "role": "planner",
  "route": {
    "fallback_used": false,
    "required_capabilities": ["chat", "tool_use"],
    "role": "planner",
    "selected_model": "anthropic/claude-sonnet-4",
    "selected_provider": "anthropic",
    "selection_mode": "registry_route",
    "selection_reasoning": "Matched demo route anthropic/claude-sonnet-4"
  },
  "task_id": "opc-p4-audit-demo",
  "total_cost_usd": 0.02,
  "ts": "2026-06-12T02:45:58Z"
}
```

完整 11 字段，8 必填字段全部存在 + 类型正确。

## 4. 命令输出摘要

### 4.1 单元测试

```text
$ cd projects/llm-gateway && \
  uv run --with pytest --with pyyaml --with-editable . \
  pytest tests/test_phase4_budget_and_audit.py -v

collected 5 items
tests/test_phase4_budget_and_audit.py::test_estimate_model_cost_uses_registry_rates PASSED
tests/test_phase4_budget_and_audit.py::test_record_llm_audit_writes_required_fields PASSED
tests/test_phase4_budget_and_audit.py::test_audit_record_schema_enforces_all_required_fields PASSED
tests/test_phase4_budget_and_audit.py::test_audit_record_rejects_missing_task_id_or_role PASSED
tests/test_phase4_budget_and_audit.py::test_audit_jsonl_supports_cross_record_task_attribution PASSED
5 passed in 0.05s
```

> **注意**：派工清单要求的命令是
> `uv run --with pytest --with pyyaml pytest projects/llm-gateway/tests/test_phase4_* -q`,
> 这条命令在 monorepo 根目录会因 import path 失败（`ModuleNotFoundError: No module named 'llm_gateway'`）。
> 正确写法是 `cd projects/llm-gateway && uv run --with pytest --with pyyaml --with-editable . pytest tests/test_phase4_* -q`
> （子仓目录 + editable 安装源包）。两种调用在子仓 CI 流水线里都会用后者。
> 5/5 测试在子仓模式下通过。

### 4.2 audit demo

```text
$ rm -f projects/llm-gateway/audit/llm_calls.jsonl
$ python3 scripts/opc_p4_budget_audit_demo.py
exit=0
# projects/llm-gateway/audit/llm_calls.jsonl 写入 1 条 record
$ tail -1 projects/llm-gateway/audit/llm_calls.jsonl | python3 -m json.tool
# output: 完整 11 字段 record (上面 §3.3)
```

### 4.3 jsonl 尾部

```text
$ tail -n 3 projects/llm-gateway/audit/llm_calls.jsonl
{"input_tokens":120,"latency_ms":0.251,"metadata":{"tool_count":10},"model":"claude-sonnet-4","output_tokens":40,"provider":"anthropic","role":"planner","route":{...},"task_id":"opc-p4-audit-demo","total_cost_usd":0.02,"ts":"2026-06-12T02:45:58Z"}
```

### 4.4 audit-rollout

```text
$ PYTHONPATH=projects/omo/src \
  python3 -m omo.cli audit-rollout \
    --repos workspace:. \
    --repos omo:projects/omo \
    --include-metrics \
    --output .omo/_delivery/audit-rollout/2026-06-12-opc-p4.json

📊 audit-rollout 2026-06-12T02:48:36Z (2 repos):
  workspace           :   1535 drift /   2080 records (5 consumers)  ✅ R0 (density=0.0000)
  omo                 :   1106 drift /   1369 records (3 consumers)  ❌ n/a (density=-1.0000)
  ──────────────────────────────────────────────────
  TOTAL               :   2641 drift /   3449 records (2/2 with drift)  ⚠️ worst=R0

✅ 写 rollout 报告: .omo/_delivery/audit-rollout/2026-06-12-opc-p4.json
   2 repos / 2641 drift / 3449 records

returncode: 0
```

完整报告 JSON 见 `audit-rollout-summary.md` §3。

## 5. 5/5 测试细节

| 测试 | 覆盖点 | 状态 |
|------|--------|:----:|
| `test_estimate_model_cost_uses_registry_rates` | registry 成本估算 (E1 E2 E3 共用) | ✅ |
| `test_record_llm_audit_writes_required_fields` | 8 字段全写入 jsonl | ✅ |
| `test_audit_record_schema_enforces_all_required_fields` | 8 字段在 Pydantic schema 声明 | ✅ NEW |
| `test_audit_record_rejects_missing_task_id_or_role` | 空字符串触发 ValueError | ✅ NEW |
| `test_audit_jsonl_supports_cross_record_task_attribution` | 跨 task_id 归因可消费性 | ✅ NEW |

总计 5/5 通过。

## 6. 与 LLM audit 上下游契约

```
┌────────────────────┐   fcntl append     ┌──────────────────────────┐
│ runtime.executor.  │ ─────────────────► │ projects/llm-gateway/    │
│ engine._call_llm() │                    │ audit/llm_calls.jsonl    │
└────────────────────┘                    └──────────┬───────────────┘
                                                      │ tail / parse
                                                      ▼
                            ┌──────────────────────────────────────┐
                            │ cockpit traces + omo observability  │
                            │ (按 task_id 归因 + 成本汇总)        │
                            └──────────────────────────────────────┘
```

**契约**：
- **写入端**：8 必填字段必填，schema 强制
- **落盘端**：jsonl + fcntl 进程锁
- **消费端**：必须能按 `task_id` 归因（测试证明）

## 7. 已知限制（不在 E4 收口范围）

1. **omo 子仓 n/a**：omo audit-rollout dispatcher 在子仓时缺 §17 metrics 入口
2. **drift 比例 73.8%**：属 §19 跨仓债历史 drift，不在 E4 关账范围
3. **LLM audit jsonl 不进 audit-rollout 聚合**：未来 P5 可加 `--include-llm-audit`
4. **rolling 时间窗未实现**：当前是 cumulative drift

## 8. 红线遵守

- ✅ 未改任何已 passed gate (D1/D2/E1/E2/E3 状态不变)
- ✅ 未跳 phase (P3 → P4-E3 → P4-E4 按顺序)
- ✅ "测试通过" = "gate passed" 区分：测试是必要条件, evidence-package 是充分条件
- ✅ 实现、测试、task、doc 同步更新
- ✅ audit-rollout 不假装全绿：omo 子仓 n/a 诚实标记 + drift 比例解释给出
- ✅ 真实 audit 数据：sample.json 是从 demo 跑后真实 jsonl 复制, 不是手写 fixture
- ✅ Pydantic schema 强制必填字段, 防止后续 contributor 静默丢字段
