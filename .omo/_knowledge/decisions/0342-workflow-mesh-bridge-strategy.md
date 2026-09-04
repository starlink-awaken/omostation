---
id: ADR-0342
title: Workflow Mesh Bridge 四阶段桥接策略
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
date: 2026-08-02
deciders: architecture-governance
supersedes: []
related:
  - 0298-external-connection-fabric-runtime-boundary.md
  - 0303-workflow-mesh-external-receipt-broker.md
  - 0304-runtime-effect-outcome-receipts.md
  - 0307-external-invocation-safety-contract.md
---

# ADR-0342: Workflow Mesh Bridge 四阶段桥接策略

## Context

eCOS v6 存在 5 条并行 workflow 通道，但仅 `workflow_dispatch.py` 一条真正接入了
Workflow Mesh。其余四条通道（ECOS executor、Agent Workflow lifecycle、Worker Dispatch、
External Connection Fabric）发射的事件要么丢失，要么从未产生。`events.jsonl` 长期为空，
Mesh 系统形同虚设。

B.D.S.K. 四角评审识别出核心风险：**如果 Mesh events.jsonl 是空的，整个 Workflow Mesh
系统就不存在。**

## Decision

采用"双桥接、一默认、一迁移"策略，分四阶段将所有 workflow 通道接入 Mesh：

### Phase 1: ECOS auto-connect + Agent Workflow bridge

- ECOS executor 默认使用 `get_default_mesh_sink()` 替代 `None`，自动发现 OMO workspace
  并连接 WorkflowMeshStore。找不到 OMO 时静默降级。
- Agent Workflow `start_run` / `closeout_run` 发射标准 Mesh 事件
  (`WorkflowRequested` / `WorkflowClosed`)，原始类型保存在 `payload.agent_event_type`。

### Phase 2: Worker Dispatch bridge

- `dispatch_task()` 在创建 dispatch YAML 后发射 Mesh 事件：
  - 有 `workflow_packet` 时：发射 `StepDispatched`（使用 packet admission context）
  - 无 packet 时（legacy 路径）：创建最小 admission grant，发射完整链
    `WorkflowRequested` -> `WorkflowAdmitted` -> `StepDispatched`
- `dispatch_admitted_workflow()` 移除冗余 `record_step_dispatch()` 调用，避免双写。

### Phase 3: Mesh 连接治理门

- 新增 `mesh_gate.py`，在 ECOS executor 治理管线中验证 Mesh 连接性。
- 默认模式：Mesh 不可用时产生 warning（非阻断）。
- 严格模式 (`ECOS_MESH_GATE_STRICT=1`)：阻断执行，返回 `MESH_GATE_BLOCKED`。
- 门控位置：X1/X2 校验之后、admission grant 之前。

### Phase 4: Scene Binding bridge

- 新增 `scene_bridge.py`，从 workflow metadata、context 或 params 提取 `scene_binding`
  (`scene_id`, `journey_id`, `outcome_metric`)。
- `mesh_agent_events.py` 和 ECOS executor 在 `WorkflowRequested` 事件中注入 scene_binding。
- 可选注入：有则注入，无则省略，不强制要求所有 workflow 都有业务场景绑定。

## Consequences

**正向:**
- 所有四条 workflow 通道的事件现在都流入 Mesh，events.jsonl 不再为空。
- 暗 dispatch 问题消除，所有 worker dispatch 可追溯。
- Mesh 连接可作为治理前置条件（渐进式收紧）。
- 业务场景绑定使 Mesh 能关联执行与产品场景。

**负向:**
- `default_mesh_sink.py` 引入 L0->L2 层依赖 (ecos -> omo)，需在 layer-contract.yaml
  登记例外。长期应通过 BOS URI 或事件总线解耦。
- Legacy dispatch 路径创建的 admission grant 是最小化的（无 capability health 检查），
  治理强度低于正规 admission 路径。
- Mesh gate strict 模式尚未默认启用，需要运行时验证后再渐进推进。

## Alternatives Considered

1. **统一入口迁移**：所有 workflow 通道迁移到 `workflow_dispatch.py`。
   否决：改动面太大，风险高，且 legacy 通道有独立调用者。

2. **事件总线解耦**：引入独立的事件总线（如 Redis Stream），各通道发到总线，Mesh 订阅。
   否决：架构改动过大，当前阶段只需让 events.jsonl 不为空。

3. **不桥接，只告警**：仅检测哪些通道未接入 Mesh 并告警。
   否决：告警不能解决问题，事件仍然丢失。
