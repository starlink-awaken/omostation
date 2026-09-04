---
id: ADR-0300
title: Adaptive Digital 副官决策循环的 Workflow Mesh 边界
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/GOVERNANCE-EVOLUTION-ROADMAP.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/agent-cli-worker-collaboration.md
---

# ADR-0300: Adaptive Digital 副官决策循环的 Workflow Mesh 边界

## 背景

治理路线图已经把 Adaptive Digital 副官定义为信息流与规则流的决策循环，但它不能成为绕过
OMO 准入、Workflow Mesh 状态机或人工签核的平行执行系统。外部知识、资料、工具和方法可以
动态进入候选池，决策循环必须把候选加工成可追溯的任务、证据和提案。

## 决策

1. 副官采用 `triage -> draft -> evaluate -> sign-off` 四段循环；每段都是 Workflow Mesh
   的可观测 StepRun，输入、规则版本、输出摘要和人工决策均可重放。
2. `bos://memory/inbox/triage`、`bos://memory/inbox/draft` 和
   `bos://persona/bdsk/evaluate` 是能力连接点，不是直接执行授权；外部资源必须先经过
   descriptor、permission、health、receipt 和 admission 合同。
3. 副官只负责理解、排序、起草、评估和生成提案；任务派发、worker 租约、过期、接管和副作用
   仍由 OMO/Workflow Mesh 的既有控制面负责。
4. 没有真实业务场景或人工签核时，候选保持 proposal/draft，不自动激活连接、不自动改变全局
   状态、不自动执行外部动作。

## 结果

这条边界允许外部知识、数据、资源、方法和工具持续扩展，而不会把系统膨胀成无边界的“万能
代理”。本轮 ADR-0301 的 worker lease watchdog 属于该决策循环的运行可靠性层，只能记录租约
过期，不能替代 coordinator 的接管决策。

## 验收

- 决策循环每段都有 Workflow Mesh run、规则/能力引用和结果证据；
- 候选连接在 activation 前保持 proposal-only，并可审计拒绝原因；
- worker 失联只进入 `lease_expired`，不会由 watchdog 自动生成 `WorkerReclaimed`；
- 真实场景激活前不新增外部副作用和长期数据写入。
