---
id: ADR-0355
title: Workflow Mesh explicit adjudication materialized into KEMS evaluation manifest
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: workflow mesh evaluation and KEMS persistence
date: 2026-08-03
---

# ADR-0355: Workflow Mesh 显式裁决评测 manifest 材料化

## Context

Phase 61 已经形成 Workflow Mesh 评测标签回执和双人放行队列，但标签事实仍停留在 OMO 运营投影，无法进入既有 KEMS
`EvaluationStore`。如果直接把 `consensus` 或运行 readiness 当成最终真值，会把“事实完整”误报成“人工确认”，并绕过真实评测集的
脱敏、版本和证据约束。

## Decision

1. OMO 新增 `workflow-mesh-evaluation-manifest/v1` 投影，按 `evaluation_id` 连接评测数据集和标签回执。
2. 只有 `review_stage=adjudication` 且最终 `decision=accept` 的样本才材料化；`consensus` 只能作为候选，不能直接进入 KEMS。
3. 样本只保留 SHA-256、`vault://redacted/` 引用、场景 ID、有限标签、运行 ID 和证据引用；原文、prompt、模型输出、凭据和自由文本不进入 manifest。
4. Cockpit 新增材料化 API，复用 KOS `EvaluationManifest`、`EvaluationSample` 和 `EvaluationStore`，不创建第二套评测数据库。
5. 没有可材料化样本时 fail-closed；材料化成功也只表示工程通路完成，不代表真实业务评测集或模型生产准入已经完成。

## Boundary

- 不训练模型、不启动预测、不修改资源路由和 Workflow Mesh admission。
- 不把 KEMS manifest 当作原始数据仓库；原始业务材料仍留在受控存储。
- M2/M6 仍受真实低风险消费者、真实 receipt、outcome feedback 和双人 adjudication 阻塞。

## Verification

- OMO: label receipt、队列和 manifest projection 定向测试通过，Ruff 通过。
- Cockpit: KEMS manifest 注册、Workflow Mesh 材料化、空结果 fail-closed 和原文拒绝测试通过。
- Cockpit UI: Workflow Mesh 材料化入口定向测试通过，组件 ESLint 和 Vite build 通过；全仓 lint 仍有既有基线问题。
