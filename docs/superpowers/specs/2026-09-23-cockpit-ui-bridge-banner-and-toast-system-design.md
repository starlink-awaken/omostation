---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: Cockpit-UI 下沉工作台统一底座导流横幅与微交互反馈体系
bet_id: BET-Y2Q2-T10-159
created: '2026-09-23'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# Cockpit-UI 下沉工作台统一底座导流横幅与微交互反馈体系

## Problem

随着治理与底层运维逻辑下沉至知行 43191 底座，Cockpit UI 工作台需要清晰表达分层边界与底座承接关系，同时缺乏轻量非侵入的微交互反馈体系。

## Solution

1. 挂载 `<GovernanceBaseBridgeBanner />` 于平台控制、基础设施、系统保障等工作台头部，提供清晰的「已下沉至知行 43191 底座」标识及来源模块标注。
2. 横幅内置一键唤起 74s 哨兵巡检实时遥测抽屉与直达知行监造大屏入口。
3. 引入轻量黑曜石微交互 Toast 体系（`<ToastProvider />` / `useToast`），支持成功、警告与通知三态反馈。
