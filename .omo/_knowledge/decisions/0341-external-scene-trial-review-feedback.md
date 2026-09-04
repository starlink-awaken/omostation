---
id: ADR-0341
title: External scene trial review feedback boundary
status: archived
type: adr
date: 2026-08-03
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
decision: "把 observation-only 场景试运行的人工评审固化为 OMO proposal-only 回执，并通过 Cockpit 只读投影和受限写入口形成可审计反馈闭环；不把评审当作执行或业务结果。"
---

# ADR-0341: 外部场景试运行审阅反馈边界

## 背景

Phase 47 已经能够把 Scene Card、外部目录和业务试运行计划固化成 `external-scene-trial/v1`，但人工评审仍可能停留
在 Cockpit 瞬时 UI 状态。缺少持久回执会导致“继续试运行”“要求补充”和“否决”无法复盘，也容易把人工查看误判为
真实消费者已经验证。

## 决策

新增 `external-scene-trial-feedback/v1`，由 OMO 追加到
`.omo/_knowledge/workflow-mesh/external-scene-trial-feedback.jsonl`。回执引用已存在的 proposal-only trial，
只允许 `continue`、`request_changes`、`reject`，必须携带评审人、评审依据和至少一条脱敏证据引用。

Cockpit 暴露：

- `GET /api/external-resources/scene-trials`：返回试运行与最新评审的只读投影；
- `POST /api/external-resources/scene-trials/review`：追加 proposal-only 评审回执。

两个入口固定 `activation=forbidden`、`provider_invocation=false`、`workflow_run_creation=forbidden`，不创建
WorkflowRun、不修改 admission、不调用 provider、不写业务成功证据。评审回执与既有
`outcome-feedback/v1` 分离：只有真实消费者产生 WorkflowRun、external receipt 和 outcome feedback 后，才允许
进入正式晋升提案。

## 结果

人工评审成为可重放、可审计的事实，且不会越过业务验证边界。没有记录返回 `empty`，存储或格式异常返回
`unavailable`，不以动态 provider 读取伪造审阅数据。

## 验证

- OMO 试运行及评审回执单元测试通过；
- Cockpit 外部资源 API 回归测试通过；
- Cockpit UI 外部资源目录与试运行审阅面单元测试、构建和 lint 通过。
