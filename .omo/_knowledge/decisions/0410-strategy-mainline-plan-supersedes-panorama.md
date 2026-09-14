---
id: ADR-0410
title: 三年战略主线归属 — Plan supersede Panorama
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-08-15
related:
  - ADR-0203
  - ADR-0210
  - ADR-0247
  - ADR-0365
type: ssot
---

# ADR-0410: 三年战略主线归属 — Plan supersede Panorama

## WHY

`docs/STRATEGY-3YEAR-PANORAMA.md`（v2.3）与
`docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`（draft）同时描述 2026H2–2029，
且 STRATEGY-INDEX 仍把 Panorama 标成「主方案」。两套北极星、两套分期、
两套成熟度判断并存，是声明≠事实在战略层的实例。

2026-08-15 grill（Q1=A, Q2=A）锁定：采纳 Plan 为主线。

## WHAT

- `STRATEGY-3YEAR-PLAN-2026H2-2029.md` 升为 `status: active` / `lifecycle: contract`，
  `supersedes: [docs/STRATEGY-3YEAR-PANORAMA.md]`。
- `STRATEGY-3YEAR-PANORAMA.md` 转为 `status: superseded`，产品结构
  （五平面、四条黄金旅程）保留为 Plan 的产品投影，不删正文。
- 唯一北极星采用 Plan §0.3 那一句，并保留其 2027-12-31 可证伪条件。
- `STRATEGY-INDEX.md` 的「主方案」标注改指 Plan。
- 本裁决不授权 gbrain+kairon 合并（grill D3 未开），不新写多机物理 ADR（D5）。

## REJECTED ALTERNATIVES

### 保留 Panorama 为主线

Rejected：其「已完成跨越」断言与交接手册/台账证据冲突，且无失败判据。

### 两者并列、互称 related

Rejected：会把「两个主方案」固化成第三种声明。

## CONSEQUENCES

- 下游文档引用「三年主方案」时以 Plan 为准。
- Wave/Gate 与 BET 的对齐另立 `BET-Y1Q1-T6-02`（candidate），本 ADR 不宣称已对齐。
