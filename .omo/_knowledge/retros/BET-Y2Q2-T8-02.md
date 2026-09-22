---
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-21
title: BET-Y2Q2-T8-02 复盘
type: retro
---
# BET-Y2Q2-T8-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 25 分钟（vs appetite 3 days）。未超出，按时完成。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| strategy_ui.js 导航死代码删除 | ✅ 已删除 (.strategy-nav-group / .strategy-nav-heading grep count = 0) |
| workbench_ui.js 导航从规范数组派生 | ✅ 从 window.ZHIXING_NAV_GROUPS 与 window.ZHIXING_NAV_LABELS 严格派生 |
| ecosystem_ui.js zhixingGroups 从规范数组派生 | ✅ zhixingGroups 与 zhixingLabel 均从规范单一权威源动态映射 |
| 所有导航锚点添加 data-asd-panel 属性 | ✅ 全部 24 个锚点均正确设置 data-asd-panel 属性 |

全部通过。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **键盘快捷键加载时序问题**: `ui_extensions.js` 原本在文件开头就尝试读取 `window.ZHIXING_NAV_GROUPS` 绑定键盘快捷键，但该全局变量却被定义在后续行，导致快捷键初始化时为空。已将其移至文件最前部优先执行。
2. **secondaryIds 标签手写漂移**: `ecosystem_ui.js` 原本手写了 15 个板块的中文名映射，与 `workbench_ui.js` 的映射不同步。现统一导出 `window.ZHIXING_PANEL_TITLES` 实现动态派生。
3. **panorama 目标态披露**: 在权威标签映射中显式标注为 `📐 白皮书指导（目标态）`，并在全景与各视图中统一展现。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
Dashboard 源码修改（`~/.local/share/zhixing-dashboard/`）：
- `ui_extensions.js`: 导航定义提升、补全 24 板块 label 及目标态标注、导出单一权威源
- `strategy_ui.js`: 彻底移除 dead nav CSS rules
- `workbench_ui.js`: 导航构建与 `data-asd-panel` 属性注入
- `ecosystem_ui.js`: `zhixingLabel` 改为从 `window.ZHIXING_PANEL_TITLES` 派生
- `template.html`: 静态兜底锚点补充 `data-asd-panel`

主仓新增/修改文件：
- `docs/superpowers/specs/2026-09-21-t8-02-dashboard-nav-unification-design.md`
- `.omo/_knowledge/retros/BET-Y2Q2-T8-02.md`
- `docs/plans/3y-bet-ledger.yaml`

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **单一权威源**: 任何导航分组与板块名称的变更，唯一修改点为 `ui_extensions.js` 中的 `window.ZHIXING_NAV_GROUPS` 与 `window.ZHIXING_NAV_LABELS`，严禁在其他 UI 文件中硬编码映射副本。
2. **目标态要求**: `panorama` 是白皮书指导目标态，非运行事实，显示时需保持诚实标注。
3. **下一步任务**: 紧随推进 `BET-Y2Q2-T8-03`（Dashboard agent-brief 接入 + orient L0 + personal 动态化）。
