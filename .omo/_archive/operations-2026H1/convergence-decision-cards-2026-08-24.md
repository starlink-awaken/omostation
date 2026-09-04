---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: CONV-3 项目收敛决策卡 (差距治理 S3)
type: doc
---

# CONV-3 项目收敛决策卡 (差距治理 S3)

> 生成: 2026-08-24 · 状态: ✅ 已决策 (用户授权 agent 定案, 2026-08-24T05:48Z)
> 背景: 复盘识别的"低成熟项目稀释健康分"差距 (S3 收敛聚焦)。
> 权威数据源: GitHub tree (避免本地 checkout 不全误判)。
> 决策授权: 用户 "继续剩余工作，你来帮我决策，给你授权" → agent 定案, 记入 waiver-2026-08-24-gap-governance.md。

## 决策原则

- 每个项目明确 "继续投入 / 收敛 / 归档" 三态, 消除"半吊子归档" (mesh-router 教训)
- 收敛聚焦: 把治理资源投到高价值项目, 不为低成熟项目持续稀释健康分
- 决策走 B.D.S.K 4-Corner + bet-ledger, 不强推

## 决策卡 1: family-hub (家庭数字枢纽)

| 维度 | 数据 |
|------|------|
| 权威规模 | 6 py 文件 (极小) |
| 版本 | 0.1.0 (早期) |
| Layer | L2 |
| 栈 | Python (FastMCP) |
| 健康分贡献 | 低 (小项目) |

**选项**:
- A. **继续投入**: 家庭场景是愿景 (LifeOS → 家庭数字枢纽), 但需明确 MVP 边界
- B. **收敛进 cockpit/agora**: 能力并入入口层 (参考 agora-dashboard 收敛先例)
- C. **归档观察**: 标记 paused, 释放治理资源

**建议**: 若家庭场景是 Phase 49+ 真实交付目标 → A; 若只是愿景占位 → C (归档观察, 不删除)。
**决策状态**: ✅ **已决策 → C 归档观察** (paused, 不删除) — 实证: 6 py 极小 + v0.1.0 + 无专属 bet (仅影响范围提及) + 愿景占位性质; 代码/gitlink 保留, Phase 49+ 家庭场景成为真实交付目标可复活. project-registry.yaml 已标 status: paused.

## 决策卡 2: metaos (编排引擎)

| 维度 | 数据 |
|------|------|
| 权威规模 | 102 py 文件 (中等) |
| Layer | L2 |
| 栈 | Python (uv, pytest) |
| 功能 | 决策门控/免疫/路由 |
| 重叠风险 | 与 omo (治理中枢) 功能语义重叠 |

**选项**:
- A. **明确边界**: 与 omo 划清 "治理执行 (omo) vs 编排决策 (metaos)", 防双轨 drift
- B. **合并进 omo**: 功能重叠面并入治理中枢
- C. **独立保持**: 保持现状但增加边界声明

**建议**: metaos 规模不小 (102 py), 不建议删除; 优先 A (边界声明 + 接口契约), 避免"两套门禁"。
**决策状态**: ✅ **已决策 → A 明确边界 + 接口契约** — 实证: 102 py 中等规模 + 2026-08-20 活跃 + 决策门控/免疫/路由功能实质存在; 不删除. metaos/BOUNDARY.md 新增 §0 职责边界契约 ("治理执行 omo vs 编排决策 metaos"), 防双轨 drift.

## 决策卡 3: mesh-router (已 deprecated 但保留)

| 维度 | 数据 |
|------|------|
| 状态 | deprecated (owner 收敛至 aetherforge) |
| 实现 | bin/_archive/2026-08-conv3/gac-mesh-router.py (无独立仓) |
| 引用 | 主仓零引用/未接线 |

**选项**:
- A. **正式归档**: 移入 bin/_archive/, 完成"半吊子归档"
- B. **删除**: 零引用, 风险低
- C. **保留观察**: 维持现状

**建议**: A (正式归档, 不删除——历史决策可追溯, 但移出活跃面)。
**决策状态**: ✅ **已决策 → A 正式归档** — 实证: deprecated + 零代码/CI/测试引用 + 完成"半吊子归档" (复盘指出的问题); 已 git mv → bin/_archive/2026-08-conv3/ + 移除 gac-mesh-router-check gate (gac-local-gate.py) + project-registry.yaml 标 status: archived.

---

## 跟进

- 决策后更新: `docs/project-registry.yaml` (status 字段) + 3Y-BET 台账 (bet-ledger)
- 每个收敛决策登记为 ADR (能力级 ADR), 保证可追溯
