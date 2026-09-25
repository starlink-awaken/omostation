---
status: active
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
title: "Spec: Panorama Wallboard Auto-rotation and Micro-interactions (BET-Y2Q2-T10-164)"
---
# Spec: Panorama Wallboard Auto-rotation and Micro-interactions (BET-Y2Q2-T10-164)

## 1. 概述与设计意图 (Overview & Intent)
治理全景大屏作为展厅、监控大屏及人类总控驾驶舱的首要视觉中心，需要支持无人值守的自动化巡检轮播（Auto-rotation），以及沉浸、平滑、零干扰的人机交互体验。

本规范定义大屏自动轮巡状态机、用户交互感知暂停机制、数字键直达、全屏毛玻璃 Toast 动效微交互。

## 2. 核心架构与功能规格 (Architecture & Specs)

### 2.1 自动巡检轮播状态机 (Auto-rotation Wallboard Mode)
- **轮播序列**: `gates` (门禁全景) -> `guardian` (74s 哨兵大屏) -> `topology` (架构拓扑) -> `bcos` (BCOS 进化链) -> `gates`。
- **默认间隔**: 25 秒/Tab。
- **轮播指示器**:
  - Header 工具栏展示 `巡航轮播` 开关按钮与呼吸态绿/橙指示灯；
  - 处于活跃轮播时展示当前视图剩余时间进度或倒计时指示。
- **人机交互感应暂停 (Interaction-aware Auto-pause)**:
  - 监听容器 `onMouseMove`、`onKeyDown`、`onClick`；
  - 检测到用户交互时，自动挂起轮播倒计时，显示“用户交互中 · 轮播已暂停”；
  - 闲置 12 秒无新输入后，平滑恢复自动轮播。

### 2.2 快捷键与直达体系 (Keyboard Shortcuts)
- **按键 `A`**: 开启/关闭自动巡检轮播。
- **按键 `F`**: 开启/退出沉浸大屏模式。
- **数字键 `1` ~ `5`**:
  - `1`: 门禁全景
  - `2`: 74s 哨兵大屏
  - `3`: 架构拓扑
  - `4`: BCOS 进化链
  - `5`: 执掌者总控

### 2.3 暗夜毛玻璃 Toast 与微交互反馈 (Micro-interactions & Toast Feedback)
- **Toast 提示系统**:
  - 在大屏全屏切换、轮播启停、快捷键切换时触发微型 Toast 浮窗；
  - 样式：`bg-slate-900/90 text-cyan-300 border border-cyan-500/30 backdrop-blur-xl shadow-2xl`，支持平滑淡入淡出（2.5 秒自消除）。
- **Tab 切换动效**:
  - 视图切换包裹 `animate-fade-in` 动效，确保视差自然平滑。

## 3. 验收标准与测试矩阵 (Acceptance Criteria & Test Matrix)
1. **单测覆盖**:
   - `PanoramaMasterView.test.tsx`:
     - 验证自动轮播开关点击与状态切换；
     - 验证快捷键 `A` 切换轮播模式；
     - 验证数字键 `1`-`5` 快速切换指定 Tab；
     - 验证 Toast 提示在全屏或轮播触发时正确显示。
2. **端到端体验**:
   - 长期挂机稳定无内存泄漏；
   - 交互恢复机制严丝合缝。
