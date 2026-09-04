---
id: ADR-0321
title: External Resource Selection 评测证据与提案边界
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../standards/external-connection-fabric.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../docs/STRATEGY-3YEAR-PANORAMA.md
  - 0320-external-resource-evaluation-and-explainable-selection.md
---

# ADR-0321: External Resource Selection 评测证据与提案边界

## 背景

Phase 27 已经能解释“为什么选择某个外部资源”，但评估结果只在请求响应中短暂存在，无法与后续
Workflow Mesh 运行、真实外部 receipt 和显式消费反馈关联。若直接把选择结果当作成功标签，会把
候选排名误当成业务质量，也会掩盖“根本没有执行”的样本。

## 决策

1. OMO 新增 `external-resource-evaluation-observation/v1` 追加日志，由
   `record_external_resource_evaluation()` 作为唯一写入 broker。记录只保存经过白名单校验的
   descriptor/health 元数据、Scene Binding、策略摘要和引用，不保存原文、凭据、模型输出或 provider
   响应；写入观察不会改变 WorkflowRun、admission、provider 或业务状态。
2. 评估观察使用稳定的 `evaluation_id` 和评估摘要去重；同一身份内容冲突时 fail-closed。可以不绑定
   WorkflowRun，表示这是候选观察而不是执行事实。
3. `external-resource-selection-eval/v1` 由真实 append-only Mesh 事件、OMO 外部 receipt 和
   `outcome-feedback/v1` 只读派生。关联优先级为显式 `workflow_run_id`、唯一 `trace_id` 匹配，最后
   保留未绑定/歧义样本；没有运行证据的样本必须标记 `not_executed`，不得标为成功。
4. 执行结果只能由 Workflow Mesh 事件和 receipt 形成，资源是否真正使用只能由 receipt 对齐判定；
   结果消费只能由显式 Outcome Feedback 判定，关闭、验证或存在证据都不能替代消费反馈。
5. Cockpit 的评估接口默认只读。只有请求体显式携带 `persist_observation=true` 才写观察；新增
   selection dataset 查询和 proposal-only 分析接口，但 proposal 不更新路由、准入或运行状态，始终要求
   人工审批。
6. cockpit-ui 以勾选框明确区分“评估候选”和“记录评估观察”，并展示观察状态与场景评测集摘要；不在
   没有真实业务场景时自动激活 provider。

## 不在本 ADR 内

- 不实现真实 provider 调用、预测模型、自动路由晋升或业务指标推断。
- 不把评估观察伪装成 `EvidenceRecorded`；真实调用仍必须走 `record_external_receipt()`。
- 不建立第二套 WorkflowRun 状态机、结果真相或外部连接注册中心。

## 验证

- OMO 评估观察、事件/receipt/反馈 join、未执行降级和 proposal-only 测试通过。
- Cockpit 评估持久化、评测集查询和 proposal-only API 测试通过。
- cockpit-ui 评估表单、观察勾选、评测摘要测试和生产构建通过。
- 全量门禁和跨子模块提交在 Phase 28 closeout 时复核；既有全量 UI lint 错误不扩大到本阶段。

## 后续

下一阶段只选择一个真实、低风险、具备连续使用窗口的 Scene Card，补齐人工选择标签、真实 receipt、
结果指标和消费反馈；先用该数据做 shadow 基线和成本/延迟/质量对比，再决定是否进入 canary。没有
真实场景时，系统继续保持观察、评测和 proposal-only，不批量接入 provider。
