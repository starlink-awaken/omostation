---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 全景治理数据契约与 TypeScript 类型体系沉淀
bet_id: BET-Y2Q2-T8-05
created: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# 全景治理数据契约与 TypeScript 类型体系设计规约

## 1. 目标与背景

在「双核归一」终极收敛工程（GOAL-DASHBOARD-SOVEREIGN-CONVERGENCE）中，首要前提是将散落在知行底座（`:43191`）和 Panorama（`:43910`）的治理数据结构，沉淀为标准、严格、强类型的 TypeScript 契约，作为后续 React 组件化和双模数据供给的坚实基石。

## 2. 核心规约内容

在 `projects/cockpit-ui/src/api/types/panorama.ts` 中固化以下模型：
1. **GateItem & GateVerdict**：精确覆盖 A1~A9、RF0、RC-DL 11 大系统门禁的结论、依据与时戳；
2. **GuardianPulse**：74s 哨兵常态守护心跳与健康指标；
3. **GovernanceAlert**：治理违规告警与严重度分级；
4. **TopologyNode & DfsqLayer**：道法术器 5+4+1+1 架构分层拓扑与 COMP 槽位契约；
5. **BcosEvolutionRecord**：BCOS 主权学习进化记录；
6. **PanoramaOverviewPayload**：统一全景姿态聚合体。

## 3. 验收标准与交付物

- `projects/cockpit-ui/src/api/types/panorama.ts` 与 `index.ts` 导出完成；
- `bun run typecheck` 0 错误 PASS。
