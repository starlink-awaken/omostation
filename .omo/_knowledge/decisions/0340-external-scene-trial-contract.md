---
id: ADR-0340
title: External scene trial contract and feedback promotion boundary
status: archived
type: adr
date: 2026-08-03
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
decision: "将真实消费者、结果指标、证据计划和回滚方案绑定为 proposal-only 的 observation-only trial，并把真实执行与 outcome feedback 作为后续独立晋升门槛。"
---

# ADR-0340: 外部场景试运行合同与反馈晋升边界

## 背景

External Connection Fabric 已能发现资源、生成 catalog、做 activation preflight 并记录观察运行，但 Scene Card 仍缺少一个可持续追踪的“试运行合同”。如果直接从 preflight 进入 admission，系统会把场景准备误认为业务验证；如果只保留浏览器状态，又无法约束消费者、指标、样本窗口、回滚和反馈方式。

## 决策

新增 `external-scene-trial/v1`，由根仓 `bin/ssot/external-scene-trial.py` 从 Scene Card、catalog 和业务-owned trial plan 生成，由 OMO `record-scene-trial` broker 追加到 `.omo/_knowledge/workflow-mesh/external-scene-trials.jsonl`。

合同必须绑定：

- `scene_id / journey_id / outcome_metric`；
- 不透明的消费者、责任人、审批人和权限引用；
- 至少两条脱敏需求/激活证据引用、preflight 引用、catalog observation id；
- 可量化指标、基线/测量引用、样本数量和观察窗口；
- 回滚引用和 `outcome-feedback/v1` 反馈合同。

当前唯一允许的阶段是 `observation_only`，唯一允许的状态是 `proposal_only`。合同固定
`activation=forbidden`、`provider_invocation=false`、`workflow_run_id=null`，不会创建 WorkflowRun、修改 admission、调用 provider 或生成业务成功证据。

## 晋升规则

只有在真实消费者实际使用、产生真实 `workflow_run_id`、external receipt 和显式 outcome feedback 后，才能把试运行结果交给既有 Workflow Mesh admission/执行链。WorkflowRun 关闭、验证通过或存在证据本身，都不能推断业务价值；反馈必须明确 `reviewed/adopted/rejected` 等消费状态和证据引用。

试运行 receipt 的 digest 排除 actor、source 和观察时间，并兼容历史 receipt 的旧 digest 计算方式，保证重试幂等和版本升级可回放。

## 验证

- OMO 试运行 broker 测试覆盖持久化、幂等、敏感字段、WorkflowRun 和 activation fail-closed；
- 根仓测试覆盖正常 trial、阻断 preflight 和不透明引用边界；
- CLI dogfood 完成 Scene Card → preflight → trial → OMO receipt 链路，结果保持 proposal-only/observation-only。
