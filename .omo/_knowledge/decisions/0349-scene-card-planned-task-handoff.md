---
id: ADR-0349
title: Scene Card planned task handoff
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: workflow-mesh scene intake and cockpit task center
date: 2026-08-03
---

# ADR-0349: Scene Card 到 OMO planned task 的场景承接

## Context

Scene Card 已经具备输入闸门和外部能力只读 preflight，但通过 `ready_for_admission_preview` 后仍停留在
页面投影，业务负责人无法把它交给既有任务治理链。若直接在 Scene Card 页面启动 Workflow，会跳过任务、审批、
能力健康和预算门禁，形成新的入口和隐式状态。

## Decision

增加 `POST /api/scene-cards/task` 作为受控承接入口。接口服务端重新运行 intake 和最新 catalog preflight，只有
preflight ready 才通过 OMO `create_planned_task` broker 创建 planned task。任务 ID 使用 Scene Card source digest
稳定派生，`source_ref` 作为幂等映射；重复请求复用同一 planned task。

任务只写入安全场景绑定、证据计划、摘要哈希和治理元数据。它不写原始业务目标、原始输入、provider 返回、提示词、
凭据或外部系统载荷。默认风险级别为 L1，调用方可以显式提高到 L2/L3，从而保留既有人工审批要求。

## Boundary

- preflight blocked/proposal-only/unavailable 时不创建 task，不写 OMO。
- planned task 创建不创建 WorkflowRun，不执行 worker，不调用 provider，不改变 activation/admission。
- 后续必须回到 Task Center，按 `WorkflowRequested -> admission preview -> approval/active -> dispatch` 继续。
- Scene Card 页面只显示安全 projection 和 task ID，不成为第二个任务状态机。

## Verification

- Cockpit `test_api_scene_cards.py`: 11 passed。
- 覆盖 ready 创建、稳定场景绑定、无原文元数据和 preflight 阻塞不写 OMO。
- UI `SceneCardIntakePanel.test.tsx`: 2 passed；承接按钮只在 ready projection 出现。
