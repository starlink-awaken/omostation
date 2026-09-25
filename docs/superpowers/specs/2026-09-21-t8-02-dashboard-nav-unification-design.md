---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: Dashboard 导航统一 + Panorama 目标态标注
bet_id: BET-Y2Q2-T8-02
created: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# BET-Y2Q2-T8-02: Dashboard 导航统一 + Panorama 目标态标注

## 目标

消除 `ui_extensions.js`、`workbench_ui.js` 与 `ecosystem_ui.js` 之间三份漂移导航数组，建立 `ZHIXING_NAV_GROUPS` 与 `ZHIXING_NAV_LABELS` 单一权威源；panorama 板块诚实标注为目标态；删除 `strategy_ui.js` 中历史遗留的导航死代码，并确保所有导航锚点均附带规范 `data-asd-panel` 属性。

## 变更范围

### 1. ui_extensions.js — 单一权威源定义
- 提升 `window.ZHIXING_NAV_GROUPS` 为导航单一权威源，完整囊括 8 个 ASD 对齐主面板（含全部次级板块）以及 2 个独立个人/工作台入口。
- 导出 `window.ZHIXING_NAV_LABELS` 与 `window.ZHIXING_PANEL_TITLES`，将 `panorama` 明确标注为 `📐 白皮书指导（目标态）`。
- 修复键盘快捷键监听在导航初始化前的加载时序问题。

### 2. strategy_ui.js — 导航死代码删除
- 删除未被任何实际 DOM 渲染使用的 `.strategy-nav-group`、`.strategy-nav-heading` 等历史遗留 dead CSS 规则。

### 3. workbench_ui.js — 统一派生与面板属性
- 导航 DOM 生成逻辑严格从 `window.ZHIXING_NAV_GROUPS` 与 `window.ZHIXING_NAV_LABELS` 派生。
- 为生成的每个导航锚点设置标准 `data-asd-panel` 属性，与 ASD 架构对齐。

### 4. ecosystem_ui.js — 消除手写板块标题副本
- `zhixingGroups` 与 `zhixingLabel` 均动态由 `window.ZHIXING_NAV_GROUPS` 与 `window.ZHIXING_PANEL_TITLES` 派生，彻底消除手写漂移映射。

### 5. template.html — 静态兜底属性对齐
- 为静态模板中的所有导航锚点补齐 `data-asd-panel` 属性。

## 验收标准

1. `cd ~/.local/share/zhixing-dashboard && cat ui_extensions.js strategy_ui.js workbench_ui.js panoramic_ui.js next_ui.js topology_ui.js mof_ui.js ecosystem_ui.js > /tmp/zc.js && node --check /tmp/zc.js` → exit 0
2. `grep -c "ZHIXING_NAV_GROUPS" ~/.local/share/zhixing-dashboard/ui_extensions.js` → >= 1
3. `strategy_ui.js` 中不存在 `.strategy-nav-group` 死代码
4. `panorama` 在导航与地图中诚实标注为目标态
5. 所有导航锚点均附带 `data-asd-panel` 属性

## 非目标

- 不修改现有业务面板内部的渲染组件与接口通信
- 不引入外部未准入的前端框架
