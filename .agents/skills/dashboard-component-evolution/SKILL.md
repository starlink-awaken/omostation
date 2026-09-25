---
name: dashboard-component-evolution
description: 全景驾驶舱与治理大屏组件开发、TS 契约映射、WAI-ARIA 1.2 无障碍规范与双模供给层演进指南。
version: 1.0.0
owner: governance-team
last-reviewed: 2026-09-25
---

# Dashboard Component Evolution Skill

> **驾驶舱前端组件演进守则**：指导 AI Agent 在 `projects/cockpit-ui` 中遵循最高工业级治理规范开发、重构或挂载全新的 Dashboard 面板与卡片。

---

## 1. 核心架构约束 (Iron Rules)

### 规则 1: 双模供给层规范 (Dual-Mode Supply)
- **要求**: 任何消费后端治理数据的组件，必须通过 `projects/cockpit-ui/src/api/hooks/useGovernancePanorama.ts` 接入。
- **严禁**: 严禁在组件内部使用直接的 `fetch` 或 `axios` 调用未经封装的 HTTP 接口。
- **降级保证**: 必须在 `FALLBACK_PANORAMA_DATA` 中提供完整的本地静态快照，确保网络闪断、端口导流或离线环境零白屏。

### 规则 2: W3C WAI-ARIA 1.2 无障碍合规
- **要求**:
  - 所有大屏 Tab 必须配置 `role="tablist"`、`role="tab"`、`role="tabpanel"`；
  - 必须绑定 `aria-selected`、`aria-controls`、`aria-labelledby`；
  - 弹窗与抽屉组件必须配置 `role="dialog"`、`aria-modal="true"`，并实现 `Escape` 键一键退出；
  - 所有按钮必须具备有语义的 `aria-label`。

### 规则 3: 沉浸大屏与自动巡航交互守卫
- **要求**:
  - 大屏自动巡检轮播周期标准为 **25s**；
  - 当检测到人类鼠标移动或键盘输入时，必须进入交互挂起态（冷却期 **12s**），严禁在人类正在阅读或点击时粗暴切页；
  - 必须支持数字键 **1-5** 直达对应 Tab，**F** 键切换壁挂全屏，**A** 键开关自动轮播，**D** 键唤起深度遥测抽屉。

### 规则 4: TypeScript 严苛类型契约
- **路径**: `projects/cockpit-ui/src/api/types/panorama.ts`
- **要求**: 所有新增字段必须在 `panorama.ts` 定义明确 interface，严禁使用 `any`。

---

## 2. 标准组件开发 4 步走流程

### Step 1: 契约扩展 (Type & Fallback)
1. 在 `projects/cockpit-ui/src/api/types/panorama.ts` 定义接口；
2. 在 `projects/cockpit-ui/src/api/hooks/useGovernancePanorama.ts` 完善 `FALLBACK_PANORAMA_DATA`。

### Step 2: 编写现代化 React 组件
在 `projects/cockpit-ui/src/views/panorama/` 下开发组件，使用 TailwindCSS + Lucide Icons，保持统一的科幻工业级设计语言（深灰底、毛玻璃边框、状态发光点）。

### Step 3: 挂载到全景大屏
在 `projects/cockpit-ui/src/views/panorama/PanoramaMasterView.tsx` 中注册 Tab 或工具按钮，并绑定键盘快捷键与无障碍标签。

### Step 4: 编写并运行 Vitest 单元测试
- **路径**: `projects/cockpit-ui/src/views/panorama/__tests__/YourComponent.test.tsx`
- **执行命令**:
  ```bash
  cd projects/cockpit-ui && npx vitest run src/views/panorama/__tests__/
  ```
- **质量门槛**: 测试套件运行时间 < 1.0s，100% PASS。
