---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
bet: BET-Y1Q4-T8-18
title: Sovereign TUI 2.0 旗舰多窗格终端控制台融合重构
symptom: 旧版 TUI 仅支持单屏简易状态展示，缺乏 8 大核心领域多窗格导航、实时数据流适配及深度 Vim 交互
solution: 基于 USP v1 表面协议重构 SovereignCockpitApp，集成 8 领域导航树、响应式卡片甲板、折叠实时日志抽屉、ctrl+p 命令面板与 Vim 键位
type: ephemeral
status: archived
---

# BET-Y1Q4-T8-18 复盘

## 做对了什么

1. **8 大领域适配器全覆盖**：在 `cockpit/tui/adapters/__init__.py` 中全面接入 USP v1 表面卡片模型（MetricGrid, DataTable, LogStream, DagGraph, ActionPanel），原生覆盖 Overview、Execution、Swarm、Compute HUD、Memory、Registry、Security、System 八大核心领域。
2. **多窗格响应式终端交互**：在 `cockpit/tui/app.py` 实现了 `DomainSidebar`（领域树）、`CardDeck`（卡片甲板）、`LogDrawer`（底部实时折叠日志抽屉）与 `CommandPalette`（ctrl+p 模糊搜索面板），支持全键盘与 Vim 导航（h/j/k/l、tab、enter、q）。
3. **兼容性保障与全面单测**：保留并重构 `CockpitTUIApp` 作为 `SovereignCockpitApp` 的直接别名，确保历史 CLI 启动入口 100% 向后兼容；新增 `tests/test_tui_app.py` 9 项针对 Textual 组件挂载、适配器数据流及 Pilot 无头交互的测试用例，配合表面协议测试全绿通过（61 passed in 0.42s）。

## 踩了什么坑

| 坑 | 修复 |
|---|---|
| Textual CSS 误写 `font-size` 属性导致解析报错（`StylesheetParseError`） | 移除无效的 `font-size` CSS 规则，改用 Textual 原生 widget 语义层级与 text-style 渲染 |
| 未挂载（not attached）的 Container 调用 `.mount()` 引发异常 | 重构 `_render_metric_grid`，在未挂载 Container 构造时将 tiles 作为位置参数传入（`Horizontal(*tiles)`） |
| USP v1 扩展按钮变体（secondary, ghost）无法直接被 Textual Button 识别 | 在 `CardDeck` 中实现变体安全降级映射，转换为 Textual 支持的 `default`, `primary`, `success`, `warning`, `error` |

## 交付自证

- 测试覆盖：`PYTHONPATH=src:../runtime/src python3 -m pytest tests/test_tui_app.py tests/test_surface_protocol.py` (61 passed)
- 门禁状态：`make gac-local-gate` 全绿通过。
