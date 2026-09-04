---
id: ADR-0333
title: Scene Card 输入到只读 activation preflight 的产品闭环
status: archived
type: decision
owner: product-architecture
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0332-scene-card-intake-gate.md
  - 0326-external-activation-preflight.md
---

# ADR-0333: Scene Card 输入到只读 activation preflight 的产品闭环

## 背景

Phase39 已经能够接收和归一化一张 Scene Card，但人工仍需手工拼接目录快照运行 preflight，
Cockpit 页面也只能评审候选，无法回答“这张业务卡片距离受治理 admission 还缺什么”。这会把
输入、目录 freshness、能力可用性和下一步动作重新分散到多个工具中。

## 决策

1. Cockpit 增加 `POST /api/scene-cards/preflight`，先复用 `scene-card-intake/v1` 闸门，再只读取
   OMO 最新 `external-resource-catalog/v1` 观察执行 `external-activation-preflight/v1`。
2. API 不接受调用方提供的目录作为运行事实，也不回退到实时 provider discovery；没有 OMO 观察时
   返回明确 `blocked` 和 `catalog_observation`，观测存储不可用时返回 `unavailable`。
3. external preflight 同步拒绝错误 Scene Card schema、请求激活的字段和非 `proposal_only` 生命周期，
   避免 API 层绕过 Phase39 输入闸门。
4. Cockpit UI 在场景卡页面增加正式输入表单和只读预检面：表单收集业务目标、旅程、消费者、责任人、
   数据范围、权限、回滚、脱敏引用、需求证据和能力标识；结果只展示 `blocked`、`proposal_only`
   或 `ready_for_admission_preview`，不提供激活、派发或写入按钮。
5. `ready_for_admission_preview` 只是材料和目录检查通过，下一步仍是人类确认后进入既有 OMO
   admission；它不等于 `admitted`、`WorkflowRun` 成功或业务结果成立。

## 验证

- 根仓 external activation preflight：10 项通过。
- Cockpit Scene Card API：9 项通过。
- Cockpit UI Scene Card 相关组件：5 项通过，生产构建通过，变更文件 ESLint 通过。
