---
id: ADR-0339
title: External catalog observation run receipt
status: archived
type: adr
date: 2026-08-03
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
decision: "将一次外部目录发现/只读探活作为独立的运行事实持久化，但不把它提升为业务成功或 WorkflowRun 证据。"
---

# ADR-0339: 外部资源只读目录观察运行回执

## 背景

外部资源目录已经能够动态发现 descriptor、执行显式只读 `health_probe`、生成目录快照并通过 OMO 持久化观察。但原有观察记录只有目录内容和变更摘要，无法回答一次运行花了多久、探活延迟如何、是否计量成本、运行是否没有任何候选，也无法将这次运行和目录 observation 稳定关联。

## 决策

新增 `external-resource-observation-run/v1`。根仓目录命令在 `--observe` 时先追加目录 observation，再通过 OMO broker 追加一条 run receipt。receipt 只保存：

- 稳定 `run_id`、`trace_id`、目录 `observation_id` 和 `catalog_digest`；
- 资源健康/不可用/错误/探活失败的计数；
- 目录运行总延迟和 provider 明确返回的 health probe 延迟摘要；
- 成本状态。当前只读发现不接入计费，因此使用 `unmetered` 和空金额，禁止伪造价格；
- `provider_business_invocation=false`、`activation=forbidden` 和是否执行 health probe。

空目录必须标为 `unavailable`，不能把“发现过程没有报错”误判为“存在可用能力”。有候选但部分不可用时标为 `degraded`，只有存在候选且没有不可用/错误时才标为 `succeeded`。

## 边界

该 receipt 不是 `external-connection-receipt/v1`，不创建 WorkflowRun，不修改 admission，不写 `EvidenceRecorded`，不读取业务原文，不承载 provider 响应或凭据。它只证明一次目录观察运行及其安全摘要；真实业务执行仍必须经过 Scene Card、OMO admission、Workflow Mesh receipt 和显式 outcome feedback。

## 验证

- OMO observation run、既有外部资源观察和扩展包回归测试通过；
- 根仓目录观察测试覆盖空目录必须 `unavailable`；
- 真实工作区 `--observe --no-health-probe` 演练在没有 provider 时生成 `unavailable` run receipt，未触发 provider 或业务调用。
