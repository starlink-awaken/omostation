---
id: ADR-0423

title: "ADR-0423: CONV-3 项目收敛 — family-hub / metaos / mesh-router 三态定案"
status: archived
lifecycle: spec
owner: governance-team
date: 2026-08-24
last-reviewed: 2026-08-24
tags: [convergence, conv3, gap-governance, project-registry, mesh-router, family-hub, metaos]
related:
  - docs/operations/convergence-decision-cards-2026-08-24.md (决策卡)
  - .omo/_truth/governance-evidence/waiver-2026-08-24-gap-governance.md (用户授权证据)
  - BET-Y1Q3-T1-06 (mesh-router 双 owner 收敛)
  - ADR-0162 (P76 Phase 7)
type: ssot
---

# CONV-3 项目收敛 — family-hub / metaos / mesh-router 三态定案

## Context and Problem Statement

S3 收敛差距治理复盘识别"低成熟项目稀释健康分"。三个项目需要明确三态 (继续投入/收敛/归档)，消除"半吊子归档" (mesh-router 教训: 标 deprecated 但保留文件 + gate 未清理)。

用户明确授权 agent 决策: "继续剩余工作，你来帮我决策，给你授权" (2026-08-24T05:48Z, 记入 waiver-2026-08-24-gap-governance.md)。

## Decision Drivers

- 每个项目必须三态明确，不留模糊地带
- 治理资源投向高价值项目，不为低成熟项目持续稀释健康分
- 决策基于实证 (GitHub tree 权威规模 / commit 活跃度 / bet 台账 / gate/CI 引用)，不臆测
- 归档 = 保留历史可追溯，移出活跃面，不删除
- 保留 gitlink / submodule 指针，未来可复活

## Evidence (权威数据)

| 项目 | 权威规模 (GitHub tree) | 最近 commit | 专属 bet | gate/CI 引用 |
|------|----------------------|------------|---------|--------------|
| family-hub | 6 py (极小) | 2026-08-21 | 无 (仅影响范围提及) | 无 |
| metaos | 102 py (中等) | 2026-08-20 (活跃) | 无 | 无 |
| mesh-router | bin/_archive/2026-08-conv3/gac-mesh-router.py (无独立仓) | deprecated | BET-Y1Q3-T1-06 已收敛至 aetherforge | gac-mesh-router-check (唯一, 已移除) |

## Considered Options

1. family-hub: A 继续投入 / B 收敛进 cockpit/agora / **C 归档观察 (采用)**
2. metaos: **A 明确边界 + 接口契约 (采用)** / B 合并进 omo / C 独立保持
3. mesh-router: **A 正式归档 (采用)** / B 删除 / C 保留观察

## Decision Outcome

1. **family-hub → C 归档观察 (paused, 不删除)**: 6 py 极小 + v0.1.0 + 无专属 bet + 愿景占位性质。代码/gitlink 保留，未来家庭场景成为真实交付目标 (Phase 49+) 可复活。project-registry.yaml 标 `status: paused`。
2. **metaos → A 明确边界 + 接口契约**: 102 py 中等规模 + 活跃 + 决策门控/免疫/路由功能实质存在，不建议删除。与 omo 划清 "治理执行 (omo) vs 编排决策 (metaos)"，防双轨 drift。metaos/BOUNDARY.md 新增 §0 职责边界契约。
3. **mesh-router → A 正式归档**: deprecated + 零代码/CI/测试引用 + 完成"半吊子归档"。`git mv` → `bin/_archive/2026-08-conv3/` + 移除 `gac-mesh-router-check` gate (gac-local-gate.py) + project-registry.yaml 标 `status: archived`。

## Confirmation

- [x] project-registry.yaml: family-hub `status: paused` + mesh-router `status: archived` + physical_location → `bin/_archive/2026-08-conv3/`
- [x] mesh-router: git mv → `bin/_archive/2026-08-conv3/` + gate 引用移除 (gac-local-gate.py 205-206 + RISK_AWARE_CHECKS 791)
- [x] metaos: BOUNDARY.md §0 职责边界契约 ("治理执行 omo vs 编排决策 metaos")
- [x] 决策卡: 待决策 → 已决策 (三项)
- [x] waiver 证据: 追加用户授权原文 + CONV-3 决策表

## Consequences

- 治理资源从低成熟项目 (family-hub) 释放，健康分不再被稀释
- mesh-router "半吊子归档" 终结，历史决策可追溯 (bin/_archive/)
- metaos 与 omo 边界明确，防双轨 drift
- 影响: gac-local-gate 移除 1 个 check (gac-mesh-router-check)，check 数下降 1；bin 脚本 -1 (归档)
