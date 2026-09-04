---
id: ADR-0322
title: Workflow Mesh 受控 Sandbox ToolPack 执行闭环
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../docs/STRATEGY-3YEAR-PANORAMA.md
  - ../../standards/external-connection-fabric.md
  - 0303-workflow-mesh-external-receipt-broker.md
  - 0307-external-invocation-safety-contract.md
---

# ADR-0322: Workflow Mesh 受控 Sandbox ToolPack 执行闭环

## 背景

Phase 28 已经可以持久化外部资源选择评估，并将真实 Mesh 事件、receipt 和结果消费反馈关联起来，
但执行侧仍只有两段独立能力：OMO 能管理 admission/worker lease，receipt broker 能接收执行方事后提交的
安全回执。当前没有一个低风险执行器验证“准入的 StepRun 被占用、执行、成功、留证和回放”这条完整路径。
业务侧真实外部场景仍处于挂起状态，因此本阶段不能用真实 provider 或私有资料充当验证样本。

## 决策

1. OMO 新增受限 `sandbox_tool_runner` 和 `omo worker sandbox-tool` 入口，唯一允许的工具是
   `sandbox.digest_ref`。它只接收 `artifact://`、`bos://` 或 `sandbox://` 引用与 64 位 SHA-256 摘要，
   不读取引用指向的原文，不接收 raw input，不执行 shell 或网络调用。
2. 执行必须绑定同一个 `workflow_run_id`、`trace_id`、`dispatch_id`、`worker_id`、`step_run_id` 和
   `admission_id`；admission 必须明确授予 `sandbox.tool.invoke`，worker 必须处于 acknowledged/active
   lease。任何上下文不匹配都 fail-closed。
3. 新增 `ToolInvocationRecorded` Mesh 事件，状态保持 `running`，保留工具、输入引用、摘要、请求摘要、
   dispatch/worker 上下文和安全开关。它不改变 OMO 的唯一状态机，也不创建第二份 WorkflowRun 真相。
4. 一次成功执行的事件顺序固定为 `StepStarted -> ToolInvocationRecorded -> WorkflowSucceeded ->
   EvidenceRecorded`。receipt 继续通过 `record_external_receipt()` 写入，使用稳定 invocation identity
   和 OMO 的幂等追加；重复请求返回 replayed，不重复追加事件或证据。
5. runner 的运行态和 Cockpit 运营投影明确标记 `activation=sandbox`、`external_side_effects=disabled`。
   sandbox receipt 只能证明执行契约和摘要计算发生，不能证明业务成功、provider 激活或结果被用户消费；
   业务价值仍必须由真实 Scene Card、独立结果证据和 Outcome Feedback 证明。
6. 真实 ToolPack/ChannelPack 接入时复用本阶段的 invocation identity、lease、receipt、失败/不可用和
   replay 边界，执行器替换为 provider adapter；provider-specific 补偿、权限和真实成本留到具体场景
   的 Scene Card 评审后处理。

## 不在本 ADR 内

- 不激活外部 provider，不导入私人 OA、邮件、SMS 或其他业务原文。
- 不实现通用脚本执行器、任意 shell、网络代理、预测模型或自动路由晋升。
- 不新增 scheduler、第二套 workflow engine、独立 receipt 存储或 Cockpit 执行真相。

## 验证

- OMO 测试覆盖成功回执、重复回放、原文/不安全引用拒绝、admission capability 缺失和 worker 上下文
  不匹配。
- 既有 worker lease、external receipt、Workflow Mesh 状态机回归测试继续通过。
- `workflow_eval`/Cockpit 只读运营投影报告 sandbox invocation 和 receipt 计数，并保持消费反馈独立。
- 通过项目测试、根目录 GaC、文档 SSOT 和 agent workflow closeout 后再提交 PR。
