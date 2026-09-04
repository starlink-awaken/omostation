---
id: ADR-0344
title: External scene consumer contract
status: archived
type: adr
date: 2026-08-03
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
decision: "以 external-scene-consumer/v1 登记真实消费者边界，并将其作为晋升就绪度的必需事实；声明不授予执行权限。"
---

# ADR-0344: 外部场景消费者契约

## 背景

试运行合同中的 `consumer_ref` 只是一个 opaque 引用，不能证明真实业务方已经准备好入口、能力、权限、指标和回滚。
如果直接把这个引用当成真实消费者，readiness 会在没有可接入业务的情况下产生误导。

## 决策

新增 `external-scene-consumer/v1`，由 OMO
`projects/omo/src/omo/omo_external_scene_consumer.py` 通过
`omo external-resources record-scene-consumer --stdin` 持久化。契约要求：

- `consumer_ref` 与 `scene_binding` 对齐；
- 声明 consumer kind、owner、entrypoint、capability、permission、metric、rollback；
- 至少一条脱敏证据引用；
- `status=declared`，并固定 `activation=forbidden`、`provider_invocation=false`、`workflow_run_id=null`。

readiness 只有在消费者契约存在且场景绑定一致时，才通过 `consumer_registered`；之后仍必须有真实 WorkflowRun、
external receipt 和 outcome feedback。契约日志使用 `consumer_id + stable contract digest` 幂等，冲突时拒绝。

## 边界

消费者声明不是 admission、WorkflowRun、provider 调用、业务结果或晋升批准。它不保存原文、凭据、输入输出或模型结果。
没有业务方提交契约时，系统保持 `blocked`，不使用内部测试或静态目录预览冒充真实消费。

## 验证

- OMO 消费者契约、readiness、试运行和反馈测试通过；
- 根仓 registry contract 测试和 doc-ssot lint 通过；
- registry、standard、Workflow Mesh implementation 文档已同步。
