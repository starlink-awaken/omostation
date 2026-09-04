---
id: ADR-0299
title: Workflow Mesh worker 租约、失效与接管证据
status: ACCEPTED
type: decision
owner: architecture-governance
created: 2026-08-02
last_updated: 2026-08-02
lifecycle: spec
related:
  - ../../standards/agent-cli-worker-collaboration.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../_truth/registry/external-connection-fabric.yaml
---

# ADR-0299 Workflow Mesh worker 租约、失效与接管证据

## Context

OMO 已能生成 admission grant、worker envelope 和 dispatch YAML，但 YAML 记录本身不是事件事实。
如果 worker 只修改操作材料，协调器无法可靠判断 ACK 是否发生、租约是否仍有效、超时是否真正发生，
也无法在接管后用同一条运行链重放和审计。外部连接也需要同样的边界：descriptor、健康与回执必须
可动态扩展，但不能越过 OMO 状态机和权限准入。

## Decision

1. `StepDispatched` 是 coordinator 到 worker 的唯一派发边界，必须绑定 `dispatch_id`、`worker_id`、
   `step_run_id` 和 `admission_id`。
2. worker 生命周期以四类事件持久化：`WorkerAcknowledged`、`WorkerLeaseRenewed`、
   `WorkerLeaseExpired`、`WorkerReclaimed`。事件与普通 Workflow Mesh 事件共用 envelope、append-only
   log、投影和幂等规则。
3. ACK 只能建立租约，续租必须基于同一 worker 身份且已有 ACK；失效只能在观测时间达到到期时间后
   发生；接管只能在失效后发生并记录 successor worker/dispatch。
4. dispatch YAML、checkpoint、stdout 和 handoff note 是操作面材料。它们可以提供恢复上下文，
   但不能单独推进 WorkflowRun 状态。
5. 对外连接继续使用 descriptor + permission_ref + health + receipt 合同。动态发现、刷新和评测
   只能增加候选或生成提案；任何 activation、admission、状态迁移和副作用都必须回到既有治理边界。

## Consequences

Worker 的租约、超时和接管可以在进程重启后从 OMO 重建，重复心跳不会产生重复事实，错误 worker 或
过早接管会被拒绝。短期代价是实际 watchdog/daemon 还需要调用已落地的 Mesh API，不能把已有 YAML
扫描器误当成自动回收闭环。

## Acceptance

- OMO 子项目 PR #10：worker lifecycle API、dispatch bridge、CLI 和测试已合并。
- `tests/test_worker_lifecycle_mesh.py` 覆盖幂等 ACK、续租、过期、接管和非法顺序。
- `tests/test_workflow_dispatch.py` 覆盖 admitted dispatch 到 `StepDispatched` 的桥接。
- 根仓文档与 `external-connection-fabric.yaml` 明确动态连接扩展不得绕过准入、回执和回滚。
