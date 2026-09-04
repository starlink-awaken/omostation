---
id: ADR-0353
title: External resource governed refresh and freshness recovery projection
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: external connection fabric and cockpit operations
date: 2026-08-03
---

# ADR-0353: 外部资源受治理刷新与 freshness 恢复投影

## Context

外部资源目录已经具备 Agora 发现、只读健康探活、OMO observation 和 observation-run receipt，但 Cockpit 只有目录读取、
复核队列和连接计划入口。用户无法明确触发一次受治理观测，也无法在页面上区分“没有观测”“观测过期”“变化待复核”和
“当前仍可继续只读评估”。继续增加连接器开关会把产品推向绕过 Workflow Mesh 的隐式激活。

## Decision

1. Cockpit 提供 `POST /api/external-resources/refresh`，只接受 actor、source、run id 和 probe 这组安全控制字段，复用
   根仓 `observe_external_resources()`，由 OMO broker 持久化 catalog observation 和 observation-run receipt。
2. Cockpit 提供 `GET /api/external-resources/refresh-status`，仅读取最新 OMO observation，派生 freshness、TTL、变化状态、
   风险码和下一步恢复动作；它不触发实时发现，不修改任何状态。
3. UI 明确区分“读取”与“受治理刷新”，刷新成功后失效所有依赖同一目录的查询。重复刷新遵循 OMO observation/run 的幂等去重，
   页面不得从返回成功推断 provider 业务成功。
4. 所有刷新路径固定保持 `activation=forbidden`、`provider_invocation=false`、`workflow_run_creation=false`、
   `worker_launch=false`。`probe=true` 只表示只读健康探活，不允许原文读取、业务写入或外部调用。

## Boundary

- freshness 过期只生成恢复建议，不自动替换资源、重试业务调用或改变准入；
- review required 只进入人工复核队列，不由刷新动作批准或激活资源；
- 真实消费者、WorkflowRun、外部 receipt、结果反馈和评测 readiness 仍是后续真实使用的必要事实；
- 定时观察、自动降级和模型化资源路由需要新的风险评估和独立 ADR，不由本阶段隐式开启。

## Verification

- Cockpit external resource API targeted tests cover governed refresh, unknown-field rejection and stale recovery projection;
- Cockpit UI full baseline test, Vite build and ESLint pass;
- root documentation SSOT and workflow verification are required before closeout.
