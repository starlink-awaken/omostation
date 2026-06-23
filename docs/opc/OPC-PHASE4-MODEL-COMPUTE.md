# OPC-P4: Model & Compute Plane

**状态**: ✅ 已完成 | **关闭时间**: 2026-06-13 11:20 CST
Status: **Gate E passed**
Signal: `opc_phase4_gate_e_passed`
**SSOT**: `.omo/tasks/done/OPC-P4-MODEL-COMPUTE.yaml`

## 目标

移除业务模块中的直接模型/供应商耦合。llm-gateway 成为唯一的模型供应商入口；compute-mesh 成为唯一的工作节点发现入口。业务代码永远不开源 `openai` / `anthropic` / `vertexai` 或直接 subprocess 推理调用。

## 子门禁

| 门禁 | 描述 | 状态 | 
|------|------|------|
| P4-E1 | Model Registry SSOT (models.yaml) | ✅ passed |
| P4-E2 | Compute Mesh Worker Discovery | ✅ passed |
| P4-E3 | 任务 budget policy 落地 | ✅ passed |

## 交付物

- `llm-gateway/src/llm_gateway/registry_data/models.yaml` — ≥10 model, 3+ provider
- `compute-mesh` — worker注册 + 5s heartbeat + 端到端 dispatch
- `scripts/opc_p4_budget_audit_demo.py` — budget 拒绝路径实测通过
- §19 debt register: `DEBT-OPC-P4-BUDGET-DEMO.yaml`

## 验证

- 20/20 executor engine tests pass
- budget audit demo exit=0
- agent-mesh/llm-gateway/compute-mesh 三仓无直接 provider import
