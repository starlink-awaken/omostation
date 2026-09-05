---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-07-28
type: ephemeral
status: archived
---

> ⚠️ **A2 SSOT 已 supersede 本文件中任何「5.4x / 协作普遍正收益」定论句**。  
> 唯一协作收益定论: [`.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md`](2026-07-29-p86-a2-collaboration-gain-map.md)  
> （5.4x 作废 · batch5 demote · 多 agent 真 dispatch 仅 3 类型 + shortfall · ADR-0289）  
> 本文件保留为历史实验记录，**不得**单独作 C 适用面依据。

# P84 K4 批次2 对照实验（协作管线 vs 单 agent）

> 上位: K4 (J3 批次2/3/4 验证协作泛化)
> 🔴 红线 (P84 §F): 协作劣于单 agent 必须如实上报送卡, 掩盖负收益=违规

## 实验
- 任务: 场景库对抗失败归因 (R/S/C 三分类, 跑 runner + 读 yaml)
- 协作管线: 3 haiku 并行 (各 A_conflict / B_failure / C_decomposition 一类)
- 单 agent: 1 haiku 顺序全 3 类

## 墙钟结果（关键）
| 模式 | 墙钟 | tool uses |
|------|------|-----------|
| 协作 (3 并行) | **223s** (max worker A) | A16 / B9 / C9 |
| 单 agent (顺序) | **128s** | 4 |

**协作 223s vs 单 128s → 协作慢 1.7x, 协作劣** 🔴

## 归因结果
| 类 | 失败数 | 归因 |
|----|--------|------|
| C_decomposition | 0 | ADV01/05 修后 ✅ |
| B_failure | 1 (ADV09) | **S** (worker B 纠正 K2 C→S) |
| A_conflict | (K2: 27) | C15 (double_claim/starvation) + S12 (orphan/unauthorized/audit_reject) |

## 诚实记录（不掩盖）
- 🔴 **协作劣于单 agent**: 简单分析任务, 协作 dispatch overhead + 木桶效应 (worker A 223s 拖累) > 单 agent 顺序高效
- **K2 被协作纠正**: worker B 细审 ADV09 C→S (inject write_conflict 首次写无冲突 + role_timeout, verdict 要求聚合 partial_failure_handled 但 inject 不自洽)
- **数据缺失诚实**: worker A / 单对照 返回"已完成"无具体 R/S/C, 老王用 K2 + worker B 纠正逻辑确认 A_conflict 分类

## 根因分析（协作劣的原因）
1. **dispatch overhead**: 3 agent launch + 等最慢 > 单 agent 直接跑
2. **木桶效应**: 协作墙钟 = max(worker), worker A 慢 (223s, 16 tool uses) 拖累整体
3. **任务粒度**: 简单分析任务单 agent 顺序已高效, 协作并行无收益

## 协作适用边界（对照实验真价值）
| 任务类型 | 协作 vs 单 | 结论 |
|---------|-----------|------|
| 独立无依赖批量 (W1 任务#1 DOC_CLAIMS) | 5.4x 优 | 协作适用 (并行收益大) |
| 简单分析归因 (K4 批次2) | 1.7x 劣 | 协作不适用 (dispatch overhead + 木桶) |

**协作非万能**: 适用独立并行任务, 不适用简单串行分析.

## 红线处置（P84 §F 送卡）
🔴 **协作劣于单 agent → 如实上报送卡**, 请人类重估协作路线适用边界:
- 协作适用: 独立无依赖批量任务 (doc 修复 / 场景生成 / 6 INTERFACE as_of)
- 协作不适用: 简单分析 / 串行审查 / 归因任务
- 建议: 按任务类型选模式 (独立并行→协作, 串行分析→单 agent), 不一刀切协作

## K4 后续批次
- 批次3 (有冲突任务): 待跑 (验证协作冲突消解是否优于单)
- 批次4 (失败注入任务): 待跑 (验证协作容错重分派)
- 批次2 已暴露协作边界 (简单分析劣), 批次3/4 验证其他场景
