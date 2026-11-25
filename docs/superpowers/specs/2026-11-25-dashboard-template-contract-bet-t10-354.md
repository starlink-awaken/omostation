---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-25
accepted: "2026-11-25 Principal 会话原话「给你授权，你帮我处理吧」+「go」— DASHBOARD-TEMPLATE-CONTRACT-GAP 债收口执行"
bet_id: BET-Y2Q4-T10-354
spec_version: 1.0.0
---

# BET-Y2Q4-T10-354 spec — 驾驶舱模板契约缺口收口（7 字段裁定 + 修复）

## 背景

债 DASHBOARD-TEMPLATE-CONTRACT-GAP（2026-11-10 立案）：template.html 以
`D.<field>` 声明 9 个顶层字段，发布 payload 全部缺席，守卫
`_check_template_data_consistency` 每次发布告警但无人处理。Wave 5（#5548）已补
`observed_at`/`refresh`（12→7 缺）。

2026-11-25 实测（live payload 114 键 + 模板引用扫描 + orchestrator.py 逐字段检索）：

- 页面数据源：`fetch('/__panorama_data__')`（panorama-collect 发布的 payload）。
- **7 字段仍 ABSENT**：anomaly_events / current_findings / library / live_sources /
  pending_publications / reconciliation_candidates / value_loop。
- 其中 6 个在 orchestrator.py **零命中** = refresh.py 时代产物（债条目
  decision_needed 原文的退役候选）。
- `live_sources` 在 orchestrator merge_results 有产出但**不进 payload**；payload
  有现成 `source_states`（21 键，含 status/observed_at）可喂同语义面板。

## 裁定表（本 spec 的核心裁定）

| 字段 | 裁定 | 依据 | 动作 |
|---|---|---|---|
| live_sources | 修兜底 | 数据在 payload source_states；模板 swarm 面板读死键恒渲染 NO_DATA | 3920: `\|\| {}` → `\|\| D.source_states \|\| {}`；4193: 去 D.live_sources 首选 |
| pending_publications | 退役 | orchestrator 零命中 | 删 JS 渲染两行 + 「等待精确人工授权」article 整卡 |
| reconciliation_candidates | 退役 | 同上 | 删 JS 渲染两行 + 「Reconciliation 候选包」card 整卡 |
| current_findings | 退役 | 同上；卡内 summary-source 仍活 | 删渲染行 + 空 ul（卡片保留） |
| value_loop | 退役 | fallback 已从 strategic.cross_plane_mesh.live_loops 派生 | `var vl=D.value_loop\|\|{}` → `var vl={}` |
| anomaly_events | 退役 | an.events 恒空，渲染恒定空态 | `var an=D.anomaly_events\|\|{}` → `var an={}` |
| library | 退役 | 库根永不到来，拼接恒等于根相对路径 | 删规范化行 + 删死拼接 |

全部动作行为等价或死面清除；页面无行为变化（除 live_sources 面板从 NO_DATA
变为真实 21 源数据）。

## 验收 (done_when)

- 模板 `D.<7字段>` 引用清零（rg 计数 = 0）。
- 守卫 dry-run（live payload + 改后模板）missing 从 7 → 0。
- `python3 bin/gac/zhixing-host-sync.py check` 维持 in_sync。

## 非目标 (non_goals)

- 不改发布器 payload（panorama-collect.py 无需变更；守卫逻辑不变）。
- 不动宿主根 stale 副本 `~/.local/share/zhixing-dashboard/template.html`
  （非 SSOT，422 行旧演化残留；release 管线用 releases/ 目录，发现时已过时）。
- 不处理 refresh.py 侧对应产出（其退役属 dashboard 部署仓事务）。

## 风险与回滚

- L1：模板单文件，revert 单提交即可；host-sync check 保证交付一致性。
