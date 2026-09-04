---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-04
last-reviewed: 2026-09-04
bet_id: BET-Y1Q4-T8-18
risk_level: L1
human_gate: false
value_indicator_policy: false
implementation_authorized: true
---

# Sovereign TUI 2.0 旗舰多窗格终端控制台架构设计规范

## 1. 目标与定位

打破原有 `app.py`、`swarm_app.py`、`compute_hud.py` 的碎片化孤岛，基于 Textual 1.x 与刚刚落地的统一表面协议 (USP v1)，打造对标 k9s / lazygit 的一站式 8 领域多窗格极客终端控制台：

- **统一单体应用**：`SovereignCockpitApp` 作为统一 TUI 入口，无缝承载全域 8 大领域数据。
- **三栏多窗格视图**：
  - **左侧导航树 (Domain Sidebar)**：8 大正交一级领域树导航，Vim 键位流 (`j`/`k`/数字键快速直达)。
  - **中央主甲板 (Card Deck)**：动态挂载基于 USP v1 的卡片原语 (MetricGrid, DataTable, DagGraph, ActionPanel)。
  - **底部实时日志抽屉 (Log Drawer)**：可折叠 (`~` 或 `ctrl+l`)，实时流式呈现系统与智能体日志。
- **全局命令面板 (Command Palette)**：`ctrl+p` 快速搜索跳转与动作触发。

## 2. 架构分层

```
+-------------------------------------------------------------------+
|                   Header: Sovereign Cockpit v2.0                  |
+---------------------+---------------------------------------------+
| Domain Sidebar      | Card Deck (USP v1 Reactive Surface)        |
|  1. Governance      |  - MetricGridCard (KPI 瓦片)                |
|  2. Agent / Swarm   |  - DataTableCard  (实体列表/任务表格)       |
|  3. Knowledge       |  - DagGraphCard   (拓扑与状态机)            |
|  4. Delivery        |  - ActionPanelCard (交互式动作按钮)         |
|  5. Compute / Mesh  |                                             |
|  6. Observability   |                                             |
|  7. System          |                                             |
|  8. Business        |                                             |
+---------------------+---------------------------------------------+
| Log Drawer (~ / ctrl+l): LogStreamCard Streaming Feed             |
+-------------------------------------------------------------------+
| Footer: [q] Quit  [1..8] Domain  [tab] Focus  [ctrl+p] Palette    |
+-------------------------------------------------------------------+
```

## 3. 验收与验证准则

- `SovereignCockpitApp` 类无语法/导入错误，能在 Textual pilot 无头模式下正常挂载运行。
- 导航树支持全部 8 大正交领域，切换领域能正确触发生命周期与视图刷新。
- 单元测试覆盖应用构建、领域切换、日志抽屉显隐及键盘绑定。
- 验证命令：`PYTHONPATH=src:../runtime/src python3 -m pytest tests/test_tui_app.py` (100% PASS)。
