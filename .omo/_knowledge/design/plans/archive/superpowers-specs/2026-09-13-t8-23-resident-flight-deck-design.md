---
schema_version: specification/v1
spec_version: 1.0.0
title: Resident Flight Deck L1-L4 授权网关 + 四维透明指挥舱
bet_id: BET-Y1Q4-T8-23
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-13
---



# Resident Flight Deck L1-L4 授权网关 + 四维透明指挥舱（BET-Y1Q4-T8-23）

## 背景（Context）

Cockpit 作为 omostation 的统一指挥入口，缺乏对 Agent 执行层的实时可见性与人工介入能力。当前 Agent 执行授权是二元（全有/全无）模式，无法根据风险等级自适应调整权限，也没有前端透明指挥舱供人类实时监控心跳、任务 DAG、算力显存遥测。

## 目标（Goal）

1. 建立 L1~L4 四阶梯自适应风险授权拦截网关（L1 只读观测 → L4 全权限执行）
2. 在 Cockpit 前端集成 Resident Flight Deck 四维透明指挥舱：心跳健康、任务 DAG 流水、算力显存遥测、人工熔断介入
3. 越权拦截率 100%，紧急人工熔断在 1 秒内生效

## 非目标（Non-Goals）

- 不允许任何未经验证的绕过命令越权执行
- 不在 Cockpit UI 中引入冗余重型第三方依赖

## 交付物

- `projects/cockpit/src/cockpit/resident_flight_deck.py` — 授权与遥测后端服务
- `projects/cockpit-ui/src/views/ResidentFlightDeck.tsx` — 前端透明指挥舱视图
- `projects/cockpit/tests/test_resident_flight_deck.py` — 单元测试
