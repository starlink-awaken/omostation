# OPC-P4: Model & Compute Plane

> Date: 2026-06-11
> Source: OPC-ROADMAP.md §M4, opc-roadmap-omo-plan.md §Phase 4
> Status: governance baseline (载体建立, 不做业务实现)
> Tracking: `.omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml`

---

## Objective

P4 removes direct model/provider coupling from business modules.
`llm-gateway` becomes the **only** model provider abstraction; `compute-mesh`
becomes the **only** worker discovery abstraction. Business code calls
`llm-gateway.chat()` and `compute-mesh.dispatch()` — never imports
`openai`, `anthropic`, `vertexai`, or runs subprocess for inference directly.

## Prerequisites

- **opc_phase3_gate_d_not_yet_passed** (P3 仍未收口; P4 不能抢先于 P3 实施业务)
  - 实际语义: P3 thin binding 跑通 (D1+D2 passed), 角色路由可在此之上叠加
- `llm-gateway` 仓存在 (already provisioned as `projects/llm-gateway/`)
- `compute-mesh` 仓存在 (already provisioned as `projects/compute-mesh/`)
- OPC-P2 §5 boundaries (5 仓记忆 + §19 跨仓债 E1-E4 收口) — done 2026-06-11

## Sub-gates

| ID | Title | Status | Evidence Requirement |
|:---|:------|:-------|:---------------------|
| P4-E1 | Model Registry SSOT | 📋 not_started | `llm-gateway/src/llm_gateway/registry/models.yaml` 含 ≥3 provider × ≥2 model per provider, 字段含 provider/model_id/context/cost/latency |
| P4-E2 | Compute Mesh Worker Discovery | 📋 not_started | `compute-mesh` ≥1 worker (本地 ollama 或 stub) registered, 5s heartbeat 跑通, ≥1 任务端到端 dispatch 成功 |
| P4-E3 | 任务 budget policy 落地 | 📋 not_started | 至少 1 个业务调用 (P3 D5 demo) 实测 budget 拒绝路径, 触发 §19 debt register |
| P4-E4 | 跨仓 audit trail 归因 | 📋 not_started | 每次 LLM 调用写入 `llm-gateway/audit/...`, 含 task_id/role/model/cost/latency, omo audit-rollout 跨仓聚合 |

## Gate Status

- `opc_phase4_gate_e_not_yet_passed` (Gate E, 区别于 P5 Gate E — 命名按 phase 隔离)

## Red Lines

- ❌ "business module 直接 import `openai` / `anthropic` / `vertexai`"
- ❌ "business module 直接 subprocess 跑 inference"
- ❌ "在 P3 Gate D 未 passed 之前申请 P4 Gate E" (Playbook §3)
- ❌ "未跑通 E1-E4 runtime 就声明 Gate E passed" (Playbook §4)
- ❌ "P4 实施跨过 E1-E4 顺序 (e.g. 先 E3 后 E1)" (E1 SSOT 是其他 E 的基础)
- ❌ "新增 provider 不在 registry.yaml" (registry 是 SSOT, 跳过它 = 漂移)

## Acceptance Package (E1-E4 全部 passed 所需)

1. `llm-gateway/src/llm_gateway/registry/models.yaml` 落地
2. `llm-gateway/src/llm_gateway/registry/role_routes.yaml` 落地
3. `compute-mesh` 至少 1 worker registered + heartbeat 实证
4. ≥1 P3 D5 demo task 跑通, audit trail 含 cost/latency/model
5. 跨仓 omo audit-rollout 报告含 4 仓 §17 metrics
6. 红线全部 hold (无 business module 绕过 llm-gateway)

## Phase Open Condition (任务 4 readiness)

P4 **可开始** 当且仅当:
- ✅ P3 D1+D2 passed (现状满足 — 2026-06-11)
- ✅ llm-gateway 仓可用
- ✅ compute-mesh 仓可用
- ✅ OPC-P2 §19 跨仓债 E1-E4 收口 (现状满足)
- ⏳ P3 Gate D 收口 (P3 D3-D5) — **不阻塞 P4 治理载体建立**, 但阻塞 P4 业务实施

P4 **blocked** (不能 claim 任何 E sub-gate):
- P3 D1/D2 退回到 not_started (不允许回退)
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

## Signal

```
opc_phase4_gate_e_not_yet_passed
opc_phase4_subgate_e1_not_started
opc_phase4_subgate_e2_not_started
opc_phase4_subgate_e3_not_started
opc_phase4_subgate_e4_not_started
```

(待 E1-E4 全部 passed 后 emit `opc_phase4_gate_e_passed`)
