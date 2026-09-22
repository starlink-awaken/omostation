---
schema_version: specification/v1
spec_version: 1.0.0
title: Dashboard agent-brief 接入 + Orient L0 + Personal 动态化
bet_id: BET-Y2Q2-T8-03
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-21'
last-reviewed: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# BET-Y2Q2-T8-03: Dashboard agent-brief 接入 + Orient L0 + Personal 动态化

## 目标

完成 Dashboard 对底层 `agent-brief` 权威事实的提取与呈现，包含：
1. 在 `refresh.py` 中解析并提取 `agent_visibility`、`safety_boundaries` 与 `next_actions` 字段；
2. 在 `workbench_ui.js` 中将 `personal` 面板的下一步三件事（next-3）从 `D.next_actions` 动态渲染；
3. 在 `template.html` 与 `ui_extensions.js` 中接入 `orient` 面板首屏 ASD L0 概览区，提供健康状态、四维指标与今日焦点。

## 变更范围

### 1. refresh.py — 提取 agent_brief 核心事实
- 在刷新流中完整提取 `agent_visibility`、`safety_boundaries` 与 `next_actions`。
- 确保快照生成后数据结构完备。

### 2. workbench_ui.js — personal 面板 next-3 动态化
- 实现 `renderPersonalNextActions`，从 `D.next_actions` 中截取前 3 项行动建议进行动态卡片渲染。
- 提取 `safety_boundaries` 进行安全限制警示渲染。

### 3. ui_extensions.js & template.html — orient 面板 L0 首屏
- 在 `#orient` 首屏挂载 `.orient-l0` 容器。
- 通过 `initOrientL0` 动态注入系统门禁健康度、主次行动引导、蜂群/BET/子模块/事件流四维概览，以及今日焦点行动卡。

## 验收标准

1. `grep -c "agent_visibility" ~/.local/share/zhixing-dashboard/refresh.py` → >= 1
2. `grep -c "D.next_actions" ~/.local/share/zhixing-dashboard/workbench_ui.js` → >= 1
3. `orient` 面板首屏显示标准 L0 块且无运行时脚本报错
4. 综合 UI JS 语法校验通过 (`node --check`)

## 非目标

- 不修改底层 agent-brief 的计算聚合算法
- 不修改既有 OMO 控制面准入逻辑
