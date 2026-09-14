---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---

> ⚠️ **A2 SSOT 已 supersede 本文件中任何「5.4x / 协作普遍正收益」定论句**。  
> 唯一协作收益定论: [`.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md`](2026-07-29-p86-a2-collaboration-gain-map.md)  
> （5.4x 作废 · batch5 demote · 多 agent 真 dispatch 仅 3 类型 + shortfall · ADR-0289）  
> 本文件保留为历史实验记录，**不得**单独作 C 适用面依据。

# P86 A2 批次3: coupled+write+negotiated 真 dispatch 对照

> 上位: P86 §A2 · goal P1 (协作收益地图, 第 3 数据点)
> 🔴 红线: 真 dispatch 口径 (3 haiku 协作 vs 1 haiku 单), 不混模拟, 禁平均, 不只跑有利

## 实验

- **任务类型**: coupled + write + negotiated (A1 分类学第 3 档)
- **任务**: 写"scenario_lib A01/ADV07 可分辨修复方案"文档
  - 协作: 3 haiku 各写一段 (问题分析/修复方案/验证计划, 各 150 字), 老王合并
  - 单 agent: 1 haiku 顺序写全方案 (400 字)
- **素材**: scenario_lib.py _handle_write 无条件产 double_claim → A01/ADV07 不可分辨
- **口径**: 真 dispatch (haiku, async, 墙钟 = max(协作) / 全程(单))

## 墙钟结果 (关键)

| 模式 | 墙钟 | tool_uses | 产出质量 |
|------|------|-----------|---------|
| 协作 (3 haiku 并行) | **115s** (max: agent1=115, agent2=103, agent3=68) | 2/agent | 1/3 有效 |
| 单 agent (1 haiku 顺序) | **140s** | 7 | **完整深入** |

**协作墙钟优 18%** (115 vs 140) — 并行轻量 (各 150 字) > 单顺序 (400 字).

## 产出质量结果 (协作的隐性劣)

| 维度 | 协作 | 单 agent |
|------|------|---------|
| 有效产出 | 1/3 (agent2) | 完整 (根因+方案+验证) |
| 空输出 | 2/3 (agent1/3 result 空, haiku 产出弱) | 0 |
| 源码定位 | 无 (agent2 给方案未定位行号) | ✅ 201-215 行精确定位 |
| 方案深度 | intent claim/propose (浅) | intent product/claim + 回归+边界+全量+单测 (深) |
| tool_uses | 2/agent (轻) | 7 (读源码+场景文件) |

**协作质量劣**: 3 个 haiku 只 1 个有效产出, 拼凑依赖个体质量; 单 agent 端到端连贯深入.

## 方案一致性 (验证 P4 方向)

- 协作 agent2: 推 inject 级 `intent` (claim/propose)
- 单 agent: 推 inject 级 `intent` (product/claim) + 源码定位 + 验证计划
- **两者都收敛到 intent 维度** ← 验证老王前版 P4 方向正确 (系统 revert 了, 但 agent 独立得出相同结论)

## 归因 (coupled+write+negotiated 的协作特性)

1. **协作墙钟微优**: coupled+write 轻量并行 (各段独立) → 并行收益 > dispatch overhead
2. **协作质量劣**: negotiated (连贯性要求高) + haiku 产出不稳定 → 拼凑质量依赖个体, 2/3 空输出拖累
3. **单 agent 深入**: 端到端连贯, 7 tool_uses 读源码+场景, 方案可执行

**结论**: coupled+write+negotiated **协作"快但浅", 单 agent "慢但深"**.
协作适用"已明确分解的轻量并行", 不适用"需连贯深入的方案设计".

## 协作收益地图 (3 数据点, 批次4 待跑)

| 批次 | 类型 | 协作墙钟 | 单墙钟 | 协作收益 | 质量 |
|------|------|---------|--------|---------|------|
| 1 | independent+none+well_defined | 快 | 慢 | **优 5.4x** | 协作优 |
| 2 | ordered+read+well_defined | 223s | 128s | **劣 1.7x** | — |
| 3 | coupled+write+negotiated | 115s | 140s | **优 18% 墙钟** | **劣 (1/3 有效)** |
| 4 | independent+write | ⬜ | ⬜ | 待跑 | — |

## 对 C 波送卡的补充

批次3 新增洞察: 协作**墙钟优 ≠ 质量优**. coupled+write 协作可能墙钟微优 (并行轻量),
但质量劣 (拼凑 + 个体不稳). 产能目标若只看墙钟会高估协作.

→ 强化 C 波建议 (`.omo/_knowledge/audits/2026-07-29-p86-c-wave-escalation.md`):
协作适用面比 A1 预测更窄 — 不仅看任务类型, 还看**质量要求** (连贯深入 → 单 agent).

## 🔴 红线遵守
- ✅ 真 dispatch (haiku, 不混模拟)
- ✅ 未只跑有利 (批次3 协作质量劣如实记录)
- ✅ 禁平均 (批次3 独立出数, 不与批次1/2 混)
- ✅ 未代批 (C 波补充送卡, 不决策)

## 待办
- ⬜ 批次4 (independent+write) 真 dispatch, 补全 4 数据点
- ⬜ 4 数据点协作收益地图定论 → C 波最终送卡
