---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: Cockpit-UI 全量功能自愈与运行时异常根治
bet_id: BET-Y2Q2-T7-04
created: '2026-09-23'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# Cockpit-UI 全量功能自愈与运行时异常根治

## Problem

`SceneGraphView.tsx` 因解构未定义属性引发 `TypeError: filter of undefined` 导致白屏，`PlatformControlWorkbench.tsx` 存在状态变量作用域溢出引发 `ReferenceError`，部分治理导出文件包含带点的非法别名，影响多路由可用性。

## Solution

1. 为 `SceneGraphView.tsx` 拓扑数据增加安全解构与优雅空状态兜底。
2. 修复 `PlatformControlWorkbench.tsx` 的闭包作用域漏洞。
3. 修正非法别名导出语法与 5 个 React Query 钩子解包逻辑。
4. 全量 82 个单元测试套件全部通过，PR #27 合入主干。
