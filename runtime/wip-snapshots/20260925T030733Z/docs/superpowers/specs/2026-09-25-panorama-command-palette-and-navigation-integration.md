# Spec: Panorama Command Palette and Navigation Integration (BET-Y2Q2-T10-163)

## 1. 概述与设计意图 (Overview & Intent)
随着治理全景主航道（`PanoramaMasterView`，`/panorama`）在 `BET-Y2Q2-T10-162` 完成核心装配与路由挂载，本规范定义 Cockpit-UI 全局导航层、命令面板（`CommandPalette`）、快捷操作面板（`QuickActionsPanel`）、侧边栏底部（`Sidebar`）以及全局快捷键体系的全面集成与双核归一收敛。

目标是让人类驾驶员（夏明星）与 AI Agent 在任何页面均可通过快捷键（⌘K、⌘P、⌘J）与显性导航入口毫秒级直达治理全景大屏及 5 大核心资产视图（门禁矩阵、74s 哨兵大屏、道法术器拓扑、BCOS 进化链、在位签署抽屉）。

## 2. 核心架构与改动点 (Architecture & Changes)

### 2.1 CommandPalette 增强 (Command & Keyword Indexing)
- **关键字与分组感知**：在 `CommandPalette` 的命令定义中增加 `keywords?: string[]` 与 `group?: string` 属性。
- **扩展检索策略**：搜索算法同时匹配 `label`、`description` 和 `keywords`，支持中文与拼音/英文术语（如 `74s`、`门禁`、`哨兵`、`bcos`、`道法术器`、`拓扑`、`dfsq`、`全景`、`panorama`）。
- **细分子命令挂载**：在命令面板中挂载治理全景 5 大子命令：
  - `治理全景: 门禁全景矩阵` -> 导航至 `/panorama?tab=gates`
  - `治理全景: 74s 哨兵巡检大屏` -> 导航至 `/panorama?tab=guardian`
  - `治理全景: 道法术器架构拓扑` -> 导航至 `/panorama?tab=topology`
  - `治理全景: BCOS 认知进化链` -> 导航至 `/panorama?tab=bcos`
  - `治理全景: 夏明星在位签署抽屉` -> 导航至 `/panorama?tab=hero`

### 2.2 全局快捷键与快捷操作集成 (Shortcuts & QuickActions)
- **快捷操作面板 (`QuickActionsPanel`)**：
  - 增加 `查看治理全景大屏`，快捷键 `Ctrl+P`，分类 `监控`，调用 `openCockpitNavigationTarget({ tab: 'Panorama' })`。
- **全局快捷键 (`useKeyboardShortcuts` in `AppLayout`)**：
  - 注册 `Ctrl+P` / `⌘P` 监听，全局一键直达 `/panorama`。

### 2.3 侧边栏底座下沉收敛 (Sidebar Convergence)
- **原生入口替代外部直连**：
  - 侧边栏底部“知行治理底座”卡片升级为原生治理大屏主入口；
  - 提供“全景大屏”原生路由导航按钮，无缝进入 `/panorama`；
  - 保留“速查”唤起右侧抽屉，实现无缝多模体验。

## 3. 验收标准与测试矩阵 (Acceptance Criteria & Test Matrix)
1. **单测覆盖**：
   - `CommandPalette.test.tsx`：验证关键词匹配、子视图命令执行与关闭逻辑；
   - `Sidebar.test.tsx`：验证侧边栏全景直达点击事件；
   - `QuickActionsPanel.test.tsx`：验证治理全景快捷动作项。
2. **端到端体验**：
   - 快捷键 ⌘P 或 ⌘K 输入 `74s` 立即显示并可回车直达 `/panorama?tab=guardian`；
   - 侧边栏全景入口可正确高亮激活态。
