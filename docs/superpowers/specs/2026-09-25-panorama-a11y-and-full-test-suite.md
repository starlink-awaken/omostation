---
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
title: "Spec: Panorama Accessibility (A11y) and Comprehensive Test Suite (BET-Y2Q2-T10-165)"
schema_version: specification/v1
status: accepted
spec_version: 1.0.0
bet_id: BET-Y2Q2-T10-165
---
# Spec: Panorama Accessibility (A11y) and Comprehensive Test Suite (BET-Y2Q2-T10-165)

## 1. 概述与设计意图 (Overview & Intent)
作为 omostation 主权治理的唯一人类总控入口，Cockpit-UI 及其治理全景大屏必须符合现代无障碍设计准则（W3C WAI-ARIA 1.2），确保视障、行动受限用户及纯键盘驾驶员均能无障碍使用全景大屏、门禁矩阵及哨兵巡检。

本规范定义 A11y 语义标准、键盘焦点导航契约以及全量单元测试与无障碍矩阵回归验证。

## 2. 无障碍与语义架构规范 (A11y Standards)

### 2.1 Tab 导航语义 (Tablist / Tab / Tabpanel Pattern)
- Tab 栏容器：`role="tablist"`，`aria-label="治理全景导航"`。
- Tab 按钮：
  - `role="tab"`
  - `id={`tab-${tab.id}`}`
  - `aria-selected={activeTab === tab.id}`
  - `aria-controls={`tabpanel-${tab.id}`}`
  - `tabIndex={activeTab === tab.id ? 0 : -1}`
- Tab 视图面板：
  - `role="tabpanel"`
  - `id={`tabpanel-${activeTab}`}`
  - `aria-labelledby={`tab-${activeTab}`}`
  - `tabIndex={0}`

### 2.2 状态开关与指示器 (Toggle Controls)
- 轮播控制按钮：`aria-pressed={isAutoRotate}`，动态 `aria-label`（如“开启自动巡检轮播”/“暂停自动巡检轮播”）。
- 大屏沉浸按钮：`aria-pressed={isWallboardMode}`，动态 `aria-label`（如“进入沉浸大屏模式”/“退出沉浸大屏模式”）。
- Toast 浮动提示：`role="status"`，`aria-live="polite"`。

## 3. 验收标准与测试矩阵 (Acceptance Criteria & Test Matrix)
1. **专项 A11y 单元测试**:
   - `src/views/panorama/__tests__/PanoramaA11y.test.tsx`:
     - 验证 `tablist`, `tab`, `tabpanel` 语义对应关系与 `aria-selected` 切换；
     - 验证 `aria-pressed` 状态与键盘无障碍操作；
     - 验证屏幕阅读器可读性。
2. **全量回归**:
   - 运行 `bun run test:unit`，93+ 个测试套件，800+ 个用例全量通过。
