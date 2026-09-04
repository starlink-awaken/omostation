---
id: ADR-0304
title: Runtime effect outcome 与 Workflow Mesh receipt 边界
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/external-connection-fabric.md
  - ./0303-workflow-mesh-external-receipt-broker.md
---

# ADR-0304: Runtime effect outcome 与 Workflow Mesh receipt 边界

## 背景

Runtime 已有稳定 effect key、append-only journal 和成功 replay，但旧实现只返回
`result/replayed`，没有结构化失败摘要，也没有一条安全路径把本地副作用结果交给 OMO 的
external receipt broker。另一方面，工具结果可能包含业务原文、模型输出或凭据相关内容，不能
直接进入 Workflow Mesh 事件或 Evidence 投影。

## 决策

1. Runtime 新增 `EffectOutcome` 和 `runtime-effect-outcome/v1` 安全摘要，固定包含 effect key、
   status、attempt、recorded_at、result digest、replayed 和 receipt eligibility；失败只保留
   error code，不保留错误原文。
2. 本地 journal 可以保留恢复工具所需的结果，但只允许通过 `safe_payload()` 或
   `external_receipt()` 跨越 Runtime 边界；这两个方法不得输出 prompt、tool arguments、原始
   provider output 或 secret。
3. 成功/降级 outcome 才能编译为 OMO 接受的 credential-free receipt；失败 outcome 只能进入
   StepFailed/BackendUnavailable 等失败状态，不能写成 `EvidenceRecorded`。
4. Runtime 不直接依赖或写入 OMO。调用方把安全 receipt 交给 `record_external_receipt()`，由
   OMO 负责 admission 上下文、事件幂等和证据投影。
5. receipt 的身份和时间使用首次成功 journal 记录派生；成功重放只改变 Runtime 返回的
   `replayed` 观察字段，不改变 receipt payload，保证 OMO 重试不会产生冲突事件。

## 不变量

- 同一 effect key 的成功副作用不会再次执行。
- 失败记录允许后续显式重试，重试次数可审计，失败不会冒充成功。
- OMO 证据只证明一次已观测的执行结果，不证明业务目标已经完成；业务验证仍需独立事件和
  outcome evidence。
- Runtime 包入口采用惰性导出，低层 journal 可以独立加载，不因 executor eager import 形成循环
 依赖。

## 验收

- Runtime effect、checkpoint、mesh lifecycle 定向测试通过。
- 根仓跨模块测试覆盖 `AgentRuntime -> safe receipt -> OMO EvidenceRecorded -> WorkflowVerified`。
- 相同 effect replay 产生稳定 receipt；失败 outcome 不具备 receipt eligibility，且不泄露错误原文。
- OMO receipt broker 的现有冲突、原文、失败和无成功运行防线保持通过。
