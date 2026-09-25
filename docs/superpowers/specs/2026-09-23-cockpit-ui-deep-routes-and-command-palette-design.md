---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: Cockpit-UI 全量受控路由深层访问恢复与全局命令面板索引升级
bet_id: BET-Y2Q2-T7-05
created: '2026-09-23'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# Cockpit-UI 全量受控路由深层访问恢复与全局命令面板索引升级

## Problem

React Router 在 `Dashboard.tsx` / `AppLayout.tsx` 之前仅遍历 `visibleRoutes` 注册路由，导致所有标记为 `hidden: true` 的深层参数化页面（如 `/scenes/:id` 场景详情、`/console` 等）被通配符拦截并强制弹回首页。同时命令面板索引受限，无法全局模糊搜索直达全量受控页面。

## Solution

1. 显式划分 `registeredRoutes` 与 `visibleRoutes`，保证全量有效页面均在 `<Routes>` 注册。
2. 命令面板全量索引 `ROUTES`，支持毫秒级全局搜索直达。
3. 单元测试全量回归，确保不破坏已有页面或重定向契约。
