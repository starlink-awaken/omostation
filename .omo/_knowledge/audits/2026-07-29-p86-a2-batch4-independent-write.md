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

# P86 A2 批次4: independent+write 真 dispatch 对照 (反转 A1 预测)

> 🔴 Q2 修正 (2026-07-29, harness bug 确认): 本文档原结论"协作 3/3 全空 = 质量劣"基于
> Agent 工具 result 字段空. **证伪发现**: agent output_file (176-269 KB, 关键字命中 12-19 次)
> 实际**含完整方案** (agent2 甚至有方案 A/B/C 对比 + ROI). result 空是 **harness 回收 bug**,
> 不是 agent 没产出.
>
> **修正**: 批次4 协作**墙钟仍劣 73%** (木桶 agent3=190s, 真实), 但**质量不劣** (3/3 产出有效方案).
> 原"双劣"修正为"墙钟劣 (木桶) + 质量不劣". 详见 `.omo/_knowledge/audits/2026-07-29-p86-q2-harness-bug-falsification.md`.
>
> 下方原文保留 (历史记录), 结论以本修正为准.

> 上位: P86 §A2 · goal P1 (协作收益地图, 第 4 数据点, 完成定论)
> 🔴 红线: 真 dispatch (3 haiku 协作 vs 1 haiku 单), 不混模拟, 禁平均

## 实验

- **任务类型**: independent + write (A1 分类学预测"协作正"档)
- **任务**: 各设计一个新 GAC check (基于 perf-budget 标准)
  - 协作: 3 haiku 各设计一个 (gate-timing / cache-hit / subprocess-count, 各 100 字)
  - 单 agent: 1 haiku 顺序设计 3 个 (共 300 字)
- **预期 (A1)**: 协作优 (independent 并行, 类似批次1 5.4x)
- **实测**: **反转预期** — 协作劣 73%

## 墙钟结果 (反转)

| 模式 | 墙钟 | 产出质量 | tool_uses |
|------|------|---------|-----------|
| 协作 (3 haiku 并行) | **190s** (max: a1=105, a2=143, a3=190) | **3/3 空** | 7-12/agent |
| 单 agent (1 haiku 顺序) | **110s** | **完整 3 check + Q4 gap 分析** | 4 |

**协作墙钟劣 73%** (190 vs 110) + **协作质量全空** (3/3 result 空).

## 为什么反转 A1 预测

A1 预测 independent+write 协作正 (并行收益). 实测劣, 原因:
1. **任务难度**: 批次1 是"简单批量" (6 INTERFACE as_of, 重复模式), 批次4 是"设计任务" (各 check 需思考逻辑). independent 但难度不同.
2. **haiku 稳定性**: 设计任务 haiku 产出不稳 (3/3 空), 简单批量 haiku 稳.
3. **木桶效应**: agent3=190s 拖累协作墙钟 (max=190), 单 agent 无木桶.

**新维度 (A1 补充)**: independent 不保证协作优, 还看**任务难度 + agent 稳定性**.
- 简单批量 (重复模式) + independent → 协作优 (批次1)
- 思考性任务 (设计/分析) + independent → 协作劣 (批次4, haiku 不稳 + 木桶)

## 4 数据点协作收益地图 (定论)

| 批次 | 类型 | 协作墙钟 | 单墙钟 | 协作收益 | 协作质量 |
|------|------|---------|--------|---------|---------|
| 1 | independent+none (简单批量 as_of) | 快 | 慢 | **优 5.4x** | 优 |
| 2 | ordered+read (失败归因分析) | 223s | 128s | **劣 1.7x** | — |
| 3 | coupled+write+negotiated (方案设计) | 115s | 140s | 优 18% 墙钟 | **劣 (1/3 有效)** |
| 4 | independent+write (check 设计) | 190s | 110s | **劣 73%** | **全空 (0/3)** |

## 定论 (C 波送卡核心依据)

> **协作管线的正收益仅在"简单独立批量" (批次1) 这一类任务上被证实.**
> **在分析 (批次2) / 方案设计 (批次3) / 思考性设计 (批次4) 上, 协作要么墙钟劣, 要么质量劣, 要么双劣.**

P84 "协作普遍正收益" 假设 **被 4 数据点否定**:
- 唯一正收益点 (批次1) 是"简单重复批量" — 协作并行收益 > dispatch overhead
- 其余 3 类 (分析/方案/设计) 协作无正收益, 甚至强负 (批次4 劣 73%)

**协作适用面极窄**: 仅"简单独立批量" (如 doc 修复 / 格式化 / 批量 as_of).
**不适用**: 任何需思考/连贯/深入的任务 (分析/设计/审查/调试).

## 对 C 波送卡的最终支撑

`.omo/_knowledge/audits/2026-07-29-p86-c-wave-escalation.md` 建议**强化**:
- 60 任务/月假设 (协作普遍正收益) **被否定**, 需按任务类型分层
- 协作仅适用简单批量, **绝大多数真实任务是思考性的 → 单 agent 更优**
- ADR-0247 协作主轴需 amend: 协作是"简单批量加速器", 非通用生产方式
- 产能爬坡: 简单批量可协作加速, 思考性任务单 agent (协作反而拖累)

## 🔴 红线遵守
- ✅ 真 dispatch (haiku, 不混模拟)
- ✅ 未只跑有利 (批次4 协作劣 73% 如实记录, 反转 A1 预测不掩盖)
- ✅ 禁平均 (4 批独立出数)
- ✅ 未代批 (定论送 C 波, 不决策)

## A2 完成
- ✅ 4 任务类型真 dispatch 对照 (批次1 历史 + 批次2 历史 + 批次3/4 本轮)
- ✅ 协作收益地图定论 (4 数据点)
- ✅ C 波送卡核心依据具备 (协作适用面极窄)
