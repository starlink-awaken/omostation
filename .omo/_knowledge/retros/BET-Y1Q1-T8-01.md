---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q1-T8-01 复盘
type: retro
---
# BET-Y1Q1-T8-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
未完成。本次会话完成了 /inbox 路由接入与 DecisionInboxView 按钮增强，但尚未 commit/PR/merge。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- ✅ /inbox 列出待裁决条目, 每条含来源/原文定位/问题清单 — 已实现。DecisionInboxView queue tab 展示 scene_name, source, raw_content, evidence_count, created_at。
- ✅ 三个按钮: 采纳 / 改后采纳 / 忽略 — 已实现。采纳调用 approveIntent，改后采纳提供 inline 编辑后 approve，忽略调用 rejectIntent（note: Ignored via cockpit-ui）。
- ✅ 改后采纳自动记录 edit_diff — 前端已支持传入 edited_content 作为 outcome_metric，后端是否持久化 edit_diff 待确认。
- ✅ 每日条目上限 5 条(防淹没, 守 R3) — 已实现。queue 通过 `.slice(0, 5)` 限制显示。

## Q3 过程中发现的与 plan 不符的事实（打假）
- DecisionInboxView 已存在于代码库中（Phase 1.5 遗留），并非从零开始。本次改造是在现有组件上增量增强。
- 后端 API 端点只有 approve/reject，没有独立的 ignore 或 approve-with-edit 端点；前端通过复用现有端点 + note 区分语义。
- `/inbox` 路由新增，与现有 `/decision-inbox` 并存，均指向 DecisionInboxView。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
待执行：`uv run --with pyyaml python bin/plan/bet-ledger.py surface`

## Q5 下一个认领本 track 的 agent 需要知道什么？
- cockpit-ui 已可 build（vite 依赖需 npm install）。
- DecisionInboxView 当前按钮布局：采纳（绿）/ 改后采纳（蓝，触发 inline 编辑）/ 忽略（红）/ 拒绝（红，次按钮）。
- 每日 5 条限制在 `queue.slice(0, 5)`，如需后端分页支持需修改 API。
- 若需区分"忽略"与"拒绝"的后端行为，需在后端新增 ignoreIntent 端点或在前端用不同 note 区分。
