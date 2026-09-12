---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-12
last-reviewed: 2026-09-12
bet_id: BET-Y1Q4-T8-24D
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T8-24D Operations 与 Mission 工作台设计

## 1. 目标

在 Cockpit-UI 六面架构（24B Store 底座 + 24C Studio 深度交付之后）交付
Operations 业务协同工作台（Work Cases 案件大厅、Scene v3 旅程状态机视图、
SpineReviewModal 署名确认、PersistentQueue 监控）与 Mission 战略交付工作台
（3Y-BET 全景矩阵、交互式甘特图、Golden Slice 真实价值公证）。

## 2. In scope

1. `projects/cockpit-ui/src/views/OperationsView.tsx`（新）：案件大厅
   （列表/状态筛选/详情抽屉）、Scene v3 旅程状态机可视化、
   PersistentQueue 深度监控面板（队列水位/延迟/死信）。
2. `projects/cockpit-ui/src/views/MissionView.tsx`（新）：3Y-BET 全景
   矩阵（按窗口/轨道分组）、交互式甘特图（窗口→BET 时间轴）、
   Golden Slice 价值公证面板。
3. `projects/cockpit-ui/src/components/operations/`（新目录）：案件卡片、
   状态机渲染、队列监控小组件。
4. `projects/cockpit-ui/src/components/mission/`（新目录）：BET 矩阵
   单元格、甘特条、公证卡片。
5. 数据面：消费既有 BOS/API 端点（signal/scene/ledger），无新后端。
6. 测试：vitest 组件测试（渲染/交互/数据契约）。

## 3. Out of scope

- 不新增后端端点；不接真实 SMTP/公钥体系。
- 不改 24B Store 契约（只消费）。

## 4. 验收

1. Operations/Mission 两视图可导航访问，组件渲染无错误。
2. 案件流转、甘特交互、公证面板三要素可演示。
3. vitest 全过 + tsc 无新增错误。
