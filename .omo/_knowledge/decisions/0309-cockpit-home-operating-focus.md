---
id: ADR-0309
title: Cockpit 首页工作焦点只读投影与日常入口
status: archived
type: decision
owner: product-architecture
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/STRATEGY-3YEAR-PANORAMA.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../projects/cockpit-ui/src/components/home/HomeFocusSection.tsx
  - ../../../projects/cockpit/src/cockpit/web/api_system_map.py
---

# ADR-0309: Cockpit 首页工作焦点只读投影与日常入口

## 背景

Cockpit 首页已经能够真实展示平台运行状态，但用户的第一日常问题不是“平台健康分是多少”，
而是“今天要处理什么、为什么、下一步是什么”。后端 SystemMap 已经生成 `project_focus`、
`project_portfolio.priority_projects`、原因和下一步动作；如果首页不消费这份投影，用户必须
先进入 SystemMap，再自行拼接任务入口，J1 仍未成为默认工作方式。

## 决策

1. 首页新增“今天需要处理”只读区，唯一数据源是 `GET /api/cockpit/system-map` 的真实投影；
   不在 cockpit-ui 重新计算项目优先级，不复制 OMO 任务状态。
2. 首页展示 SystemMap 的待处理队列、数量、原因、优先项目和 `next_action`，并将项目导航到
   既有 SystemMap 聚焦入口、将任务导航到既有 TaskCenter，不新增平行任务系统。
3. SystemMap 不可用、响应不完整或没有可信数据时，首页显示 loading、partial、unavailable
   或真实空态；禁止生成默认项目、默认队列或基于静态文案推断焦点。
4. 本区只提供人类消费和导航，不执行任务、不派发 worker、不改变 OMO 状态。真正执行必须
   继续经过 TaskCenter、Agent Workflow、OMO admission 和现有证据链。
5. `project_focus` 是当前工程治理场景的可消费投影，不代表外部业务场景已经激活；外部
   Knowledge/Tool/Channel 仍需独立 Scene Card 和真实消费者证据。

## 不变量

- 首页焦点失败不会被健康摘要、告警或任务接口的成功掩盖，焦点区独立显示 unavailable。
- 完整真实响应且队列为空时，才显示真实的“当前没有待处理项目”；接口失败时只能显示没有可展示
  的真实焦点。
- 点击项目和任务只产生已有导航目标，不直接写入任务、运行或治理状态。
- 焦点展示的原因和下一步必须来自 SystemMap 事实，不得以 UI 内置默认文本替代，除非是对空字段
  的明确不可执行提示。

## 验收

- 首页测试覆盖 loading、全源 unavailable、partial 和真实 SystemMap 焦点 4/4 通过。
- cockpit-ui 全量 Vitest：148 passed、1 skipped；生产构建通过；本轮改动文件精确 lint 通过。
- 本 ADR 不声称 J1 已完成，只把现有 SystemMap 投影接入首页；连续真实工作闭环和结果消费仍是
  后续 M1 验收条件。
