---
id: ADR-0320
title: External Resource 评估与可解释选择边界
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
  - 0319-external-resource-observation-surfaces.md
---

# ADR-0320: External Resource 评估与可解释选择边界

## 背景

Phase 26 已经能把外部资源目录、健康观察和 Scene Card 候选交给 Cockpit 消费，但只能看到资源状态，
不能解释某项能力在具体场景下为什么被选中、为什么排除其他候选。若直接把 `route()` 的最终结果展示
出来，会丢失淘汰原因，也容易把候选排序误认为业务质量或执行成功。

## 决策

1. Agora `ExternalConnectionCatalog.evaluate_candidates()` 作为唯一的场景化资源评估算法，输出
   `external-resource-evaluation/v1`。
2. 评估必须包含全候选、稳定原因码、决策因子、排序、策略摘要、`trace_id`、场景绑定和汇总计数。
3. 既有 `route()` 复用评估结果，只保留兼容的 `RouteDecision` 形状，不维护第二套选择逻辑。
4. 根仓 `evaluate_external_resources()` 负责将安全目录快照转换为 Agora 评估；Cockpit 的
   `POST /api/external-resources/evaluate` 和 UI 负责只读的人机消费。
5. 评估固定声明 `mode=read_only_evaluation`、`activation=forbidden`，不得调用 provider、写 OMO、
   创建 WorkflowRun、改变 admission 或产生业务副作用。
6. 评估只使用 descriptor/health 等安全元数据。原文、凭据、provider 响应和模型输出禁止进入评估
   结果；真实质量标签、调用回执和业务结果必须在独立的评测与证据闭环中采集。

## 不在本 ADR 内

- 不实现真实 provider 调用、业务写入或自动激活。
- 不把候选排名作为预测标签、质量结论或 admission 证据。
- 不引入独立推荐引擎、第二套路由器或新的运行状态真相。

## 验证

- Agora 外部连接测试：16 passed。
- 根仓目录评估测试：6 passed。
- Cockpit 外部资源 API 测试：17 passed。
- cockpit-ui 评估组件测试：3 passed，构建通过，变更文件 lint 通过。
- 以上测试均验证只读边界；全仓 UI lint 仍有既有无关错误，未在本阶段扩大修复面。

## 后续

下一阶段以一个真实低风险 Scene Card 为边界，建立候选选择标注、实际 receipt、结果指标和人工反馈的
最小评测集；先做 shadow 对比，再决定是否进入 canary。没有真实业务场景时继续保持目录观察和只读
评估，不批量接入 provider。
