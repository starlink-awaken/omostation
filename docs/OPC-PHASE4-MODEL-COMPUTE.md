# OPC-P4: Model & Compute Plane

> Date: 2026-06-11 (last updated 2026-06-12 Gate E closed)
> Source: OPC-ROADMAP.md §M4, opc-roadmap-omo-plan.md §Phase 4
> Status: **Gate E passed (2026-06-12)** — E1-E4 all closed
> Tracking: `.omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml`

---

## Objective

P4 removes direct model/provider coupling from business modules.
`llm-gateway` becomes the **only** model provider abstraction; `compute-mesh`
becomes the **only** worker discovery abstraction. Business code calls
`llm-gateway.chat()` and `compute-mesh.dispatch()` — never imports
`openai`, `anthropic`, `vertexai`, or runs subprocess for inference directly.

## Prerequisites

- **opc_phase3_gate_d_passed** (P3 已收口, P4 可以正式进入 E1-E4)
- `llm-gateway` 仓存在 (already provisioned as `projects/llm-gateway/`)
- `compute-mesh` 仓存在 (already provisioned as `projects/compute-mesh/`)
- OPC-P2 §5 boundaries (5 仓记忆 + §19 跨仓债 E1-E4 收口) — done 2026-06-11

## Sub-gates

| ID | Title | Status | Evidence Requirement |
|:---|:------|:-------|:---------------------|
| P4-E1 | Model Registry SSOT | ✅ passed | `llm-gateway/src/llm_gateway/registry_data/models.yaml` 含 ≥3 provider × ≥2 model per provider, 字段含 provider/model_id/context/cost/latency；`runtime.executor.engine._call_llm()` 已通过 role route 接入 |
| P4-E2 | Compute Mesh Worker Discovery | ✅ passed | `compute-mesh` ≥1 worker (本地 stub) registered, 5s heartbeat 跑通, ≥1 任务端到端 dispatch 成功 |
| P4-E3 | 任务 budget policy 落地 | ✅ passed (2026-06-12 closeout) | 业务调用 (P3 D5 demo) 实测 budget 拒绝路径 + 触发 §19 debt register; `_call_llm()` 治理字段齐 5 项 (task_id/budget_usd/estimated_cost_usd/model/debt_path); 20/20 executor engine tests pass; 复用策略: 同 task_id = 同 debt ID + occurrence_count/first_seen_at 持久; evidence: `.omo/tasks/registry/done/OPC-P4-E3/evidence-package.md` |
| P4-E4 | 跨仓 audit trail 归因 | ✅ passed (2026-06-12 closeout) | 每次 LLM 调用写入 `llm-gateway/audit/llm_calls.jsonl` (fcntl 进程锁); `LLMCallAuditRecord` Pydantic schema 强制 8 必填字段 (task_id/role/provider/model/input_tokens/output_tokens/total_cost_usd/latency_ms) + ts/route/metadata; 5/5 llm-gateway P4 audit tests pass; omo audit-rollout 5 仓聚合 (workspace R0 + omo R0 + llm-gateway R0 + compute-mesh R0 + runtime R0); evidence: `.omo/tasks/registry/done/OPC-P4-E4/evidence-package.md` + `audit-rollout-summary.md` + `llm-audit-sample.json` + `.omo/_delivery/audit-rollout/2026-06-12-5repos.json` |

## Gate Status

- ✅ `opc_phase4_gate_e_passed` (Gate E, 区别于 P5 Gate F — 命名按 phase 隔离)
- 关闭时间: 2026-06-12T02:55:00Z
- 关闭依据: E1-E4 全部 passed + 三面一致 (docs/omo tests/projects) 验证

## Red Lines

- ❌ "business module 直接 import `openai` / `anthropic` / `vertexai`"
- ❌ "business module 直接 subprocess 跑 inference"
- ❌ "在 P3 Gate D 未 passed 之前申请 P4 Gate E" (Playbook §3)
- ❌ "未跑通 E1-E4 runtime 就声明 Gate E passed" (Playbook §4)
- ❌ "P4 实施跨过 E1-E4 顺序 (e.g. 先 E3 后 E1)" (E1 SSOT 是其他 E 的基础)
- ❌ "新增 provider 不在 registry.yaml" (registry 是 SSOT, 跳过它 = 漂移)

## Acceptance Package (E1-E4 全部 passed 所需)

1. `llm-gateway/src/llm_gateway/registry_data/models.yaml` 落地 ✅
2. `llm-gateway/src/llm_gateway/registry_data/role_routes.yaml` 落地 ✅
3. `compute-mesh` 至少 1 worker registered + heartbeat 实证 ✅
4. ≥1 P3 D5 demo task 跑通, audit trail 含 cost/latency/model ✅
5. 跨仓 omo audit-rollout 报告: 5 仓 §17 metrics 聚合 ✅ (本轮 2026-06-12 推进)
   - 落 .omo/_delivery/audit-rollout/2026-06-12-5repos.json (5/5 with metrics, 0 n/a)
   - 5 仓 health_grade:
     - workspace: R0 (4 debt/4 records)
     - omo: R0 (1553 drift/2427 records, 全部 locked)
     - llm-gateway: R0 (0 drift/1 record, 4 test files)
     - compute-mesh: R0 (0 drift/3 records, 3 test files, stub R0 占位)
     - runtime: R0 (0 drift/17 records, 10 test files)
   - 实现: scripts/opc_section17_metrics.py + scripts/opc_audit_rollout_5repos.py
   - 2026-06-12 复验: "2 仓 rollout 报告 vs 4 仓声明" 反证已修
6. 红线全部 hold (无 business module 绕过 llm-gateway) ✅

## Phase Open Condition (任务 4 readiness)

P4 **可开始** 当且仅当:
- ✅ P3 Gate D passed (现状满足 — 2026-06-12)
- ✅ llm-gateway 仓可用
- ✅ compute-mesh 仓可用
- ✅ OPC-P2 §19 跨仓债 E1-E4 收口 (现状满足)
- ✅ Gate E 仅允许从 E1 起顺序推进

P4 **blocked** (不能 claim 任何 E sub-gate):
- P3 Gate D 退回到 not_yet_passed (不允许回退)
- llm-gateway/compute-mesh 仓未拉取

P4 **final close condition** (Gate E passed):
- E1-E4 全部 runtime 实证
- 验收包 6 项全有 evidence
- 红线 6 项全 hold

## Forbidden Premature Claims

- ❌ "P4 实施完成" 在 E1-E4 未全部 passed 之前
- ❌ "LLM 路由统一" 在 E1 models.yaml 未落地之前
- ❌ "成本可视化" 在 E4 audit trail 归因未跑通之前
- ❌ "business code 切到 llm-gateway" (这是 E3 实装后业务侧动作, 不属 P4 范围)

## Current Delta (2026-06-12)

- `registry.py` 作为 Python 模块已经存在，因此 `src/llm_gateway/registry/models.yaml` 这条原规划路径不可落地
- E1 SSOT 路径改为 `src/llm_gateway/registry_data/`
- `models.yaml` + `role_routes.yaml` 已创建为 P4-E1 的静态入口
- `llm_gateway.registry_data_loader` 已能把静态 YAML 加载进 `ModelRegistry`
- CLI 已新增两条可验证路径：
  - `uv run python -m llm_gateway.cli list --registry-data`
  - `uv run python -m llm_gateway.cli route --role reviewer --capability reasoning`
- `runtime.executor.engine._call_llm()` 不再直接使用 `detect_backends()[0]`；它现在先按 role/capability 走 `llm_gateway.registry_data_loader.route_role_request()`，再映射到可用 provider，必要时才 fallback
- 这使得 runtime executor 成为 P4-E1 的首条真实业务执行路径；因此 E1 已 passed
- `compute-mesh` 已补齐最小 worker 面：`WorkerRegistry` + `TaskDispatcher` + `compute_mesh.api.cli worker-demo --json`
- `worker-demo` 已实证输出 `worker_registered=true`、`heartbeat_interval_sec=5`、`dispatch_status=dispatched`；因此 E2 已 passed
- E3 closeout (2026-06-12): budget policy 治理化
  - `engine._maybe_enforce_budget()` 拒绝路径现输出 5 项治理字段 (task_id/budget_usd/estimated_cost_usd/model/debt_path) 到 `route_info.budget_policy`
  - `_register_budget_debt()` 落地复用策略: 同 task_id 永远映射到同 debt ID, 重复触发 in-place 刷新 `occurrence_count` + 持久 `first_seen_at` + 推进 `last_seen_at`, 避免无限新增垃圾 debt 文件
  - 业务路径走 llm-gateway (`from llm_gateway.registry_data_loader import estimate_model_cost`)，不直调 provider
  - 拒绝路径返回结构化 error dict, 绝不抛 traceback
  - 20/20 `projects/runtime/tests/test_executor_engine.py` pass (3 新增 closeout 测试)
  - `scripts/opc_p4_budget_audit_demo.py` 跑通, debt 文件落 `.omo/debt/items/DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO.yaml`
  - 完整证据包: `.omo/tasks/registry/done/OPC-P4-E3/evidence-package.md`
- E4 closeout (2026-06-12): LLM audit trail 跨仓归因闭环
  - `LLMCallAuditRecord` Pydantic schema 强制 8 必填字段: task_id/role/provider/model/input_tokens/output_tokens/total_cost_usd/latency_ms (+ ts UTC Z + route + metadata)
  - 空字符串 task_id/role 触发 ValueError (schema-level guard, 防止 contributor 静默丢字段)
  - `_append_jsonl()` 用 fcntl 进程锁保证并发写安全
  - 5/5 `projects/llm-gateway/tests/test_phase4_budget_and_audit.py` 通过 (3 新增 closeout 测试: schema 全字段声明 / 空字符串拒绝 / 跨 task_id 归因)
  - 真实 audit 样本: `opc-p4-audit-demo` task → 1 条 record, 11 字段齐全
  - `omo audit-rollout` 5 仓聚合 (`workspace:.` + `omo:projects/omo` + `llm-gateway:projects/llm-gateway` + `compute-mesh:projects/compute-mesh` + `runtime:projects/runtime`): 5 仓全 R0, 0 n/a. 落 .omo/_delivery/audit-rollout/2026-06-12-5repos.json
  - 完整证据: `.omo/tasks/registry/done/OPC-P4-E4/evidence-package.md` + `audit-rollout-summary.md` + `llm-audit-sample.json`
- **Gate E closed 2026-06-12**: E1-E4 全部 passed
  - `opc_phase4_gate_e_passed` signal 已 emit
  - `opc_phase5_gate_f_pending` 启动条件已满足
  - 三面一致 (docs/omo tests/projects) 验证: `python3 -m pytest projects/omo/tests/test_opc_p3_thin_binding_demo.py projects/omo/tests/test_opc_phase_governance_alignment.py -q` → 8/8 passed

## Evidence Snapshot

- 静态 registry / route:
  - [`models.yaml`](/Users/xiamingxing/Workspace/projects/llm-gateway/src/llm_gateway/registry_data/models.yaml)
  - [`role_routes.yaml`](/Users/xiamingxing/Workspace/projects/llm-gateway/src/llm_gateway/registry_data/role_routes.yaml)
  - [`registry_data_loader.py`](/Users/xiamingxing/Workspace/projects/llm-gateway/src/llm_gateway/registry_data_loader.py)
- 首条业务接入:
  - [`engine.py`](/Users/xiamingxing/Workspace/projects/runtime/src/runtime/executor/engine.py)
  - [`test_executor_engine.py`](/Users/xiamingxing/Workspace/projects/runtime/tests/test_executor_engine.py)
- compute-mesh worker substrate:
  - [`registry.py`](/Users/xiamingxing/Workspace/projects/compute-mesh/src/compute_mesh/worker/registry.py)
  - [`dispatcher.py`](/Users/xiamingxing/Workspace/projects/compute-mesh/src/compute_mesh/scheduler/dispatcher.py)
  - [`cli.py`](/Users/xiamingxing/Workspace/projects/compute-mesh/src/compute_mesh/api/cli.py)
  - [`test_worker_registry.py`](/Users/xiamingxing/Workspace/projects/compute-mesh/tests/test_worker_registry.py)
  - [`test_dispatcher.py`](/Users/xiamingxing/Workspace/projects/compute-mesh/tests/test_dispatcher.py)
  - [`test_cli_worker_demo.py`](/Users/xiamingxing/Workspace/projects/compute-mesh/tests/test_cli_worker_demo.py)
- 验证命令:
  - `uv run --with pytest --with pyyaml pytest tests/test_phase4_registry_data.py tests/test_phase4_registry_loader.py tests/test_phase4_cli_registry_route.py -q`
  - `python3 -m pytest projects/runtime/tests/test_executor_engine.py -q`
  - `uv run --with pytest pytest tests/test_worker_registry.py tests/test_dispatcher.py tests/test_cli_worker_demo.py -q`
  - `uv run python -m compute_mesh.api.cli worker-demo --json`

## Signal

```
opc_phase4_gate_e_passed        # 2026-06-12 Gate E closed
opc_phase4_subgate_e1_passed
opc_phase4_subgate_e2_passed
opc_phase4_subgate_e3_passed
opc_phase4_subgate_e4_passed
```

(待 E1-E4 全部 passed 后 emit `opc_phase4_gate_e_passed`)
