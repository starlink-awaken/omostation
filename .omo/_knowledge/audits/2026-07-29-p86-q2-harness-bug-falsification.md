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

# P86 Q2: A2 结论证伪测试 — harness bug 确认, 批次4 重判

> 上位: goal Q2 (A2 定论前必做证伪)
> 🔴 红线 (Q2): 未排除 harness 缺陷前, 不得把"协作不适用思考性任务"写定论
> 结论: **harness bug 确认** (result 回收缺陷), A2 批次4"全空"是假象, 定论需修正

## 证伪测试设计

goal Q2 质疑: 批次4 协作 3/3 result 全空 ("任务完成"/"无后续动作") = 疑似 harness 缺陷
(输出截断 / 未回收 / 上下文未传递), 不是协作真不行.

查证: grep agent output_file (不全 Read 防 overflow), 看是否真产出方案文本.

## 证据: agent output_file 实际产出 (result 没回收)

| 协作 agent | output_file 大小 | 关键字命中 | result 字段 | 实际产出? |
|-----------|----------------|----------|------------|----------|
| agent1 (gate-timing) | 176 KB | 12 | "无后续动作" (空) | ✅ **完整方案** |
| agent2 (cache-hit) | 269 KB | 17 | "任务完成" (空) | ✅ **完整方案 (含 3 方案对比)** |
| agent3 (subprocess-count) | 228 KB | 19 | "完成" (空) | ✅ **完整方案** |

**3/3 agent 都实际产出完整方案**, 在 output_file, 但 result 字段只回收了摘要.

## 产出质量证据 (output_file 提取片段)

**agent1 (gate-timing)**:
- 完整设计: id/command/perf_budget_s + 核心逻辑 (subprocess 计时 + ci_only 分析)
- 深入考量: "实测每个 gate 需跑 subprocess 计时, 这本身可能慢 (3 gate × 2s = 6s),
  所以 check 本身需 ci_only: true 或静态分析+采样"

**agent2 (cache-hit)** — 比单 agent 更深:
- **方案 A/B/C 对比**: A=cache 文件扩 hits/misses / B=ts TTL / C=git log 推断调用次数
- 选 A + ROI 评估: "producer-coupled 但只改 1-2 个 producer check, ROI 高"
- 判定矩阵 + baseline grace + producer 配套 3 行改造 (check-severity-registry 加 meta.{hits,misses})

**agent3 (subprocess-count)**:
- 完整设计: 循环内 spawn 单独计数 (直击 N×M 病根) + warn 不 fail + 静态 AST 零 spawn 自省
- SSOT 意识: "落地需在 sgf-policy.yaml::gates 注册一行 (该 YAML 才是 gate SSOT)"

## 结论: harness bug 确认

> **Agent 工具的 result 字段回收不完整** — agent 实际产出在 output_file, 但 result 只放摘要
> ("任务完成"/"无后续动作"). 不是 agent 没产出, 是 harness 没回收.

**证据**: output_file 176-269 KB + 关键字命中 12-19 次 + 产出片段质量高 (含方案对比/ROI/SSOT).

## 批次4 重判 (基于 output_file, 非 result)

| 维度 | 原结论 (result 空) | 重判 (output_file 有产出) |
|------|------------------|------------------------|
| 协作产出 | 3/3 空 (全失败) | **3/3 完整方案** (部分超单 agent) |
| 协作质量 | 劣 | **不劣** (agent2 方案对比最深入) |
| 协作墙钟 | 190s (劣 73%) | 190s (仍劣, 木桶 agent3=190s) |
| **综合** | **双劣 (墙钟+质量)** | **墙钟劣 (木桶), 质量不劣** |

**批次4 修正**: 协作墙钟劣 73% (木桶效应, agent3 慢), 但**质量有效** (3/3 产出, 非空).
原"全空 = 协作不适用思考性任务"结论 **推翻**.

## A2 定论修正 (Q2 红线遵守)

🔴 **原定论 (基于 result 空, 撤回)**: "协作不适用思考性任务 (批次4 全空)"

✅ **修正定论 (基于 output_file 产出)**:
- 协作**墙钟**: 简单独立批量优 (批次1 5.4x), 其余墙钟劣 (木桶: 批次2/3/4)
- 协作**质量**: 原以为劣 (result 空), **实际不劣** (output_file 有产出, harness bug 致假空)
- 协作适用面: **墙钟劣 (思考性任务木桶效应), 但质量 OK**
- → 协作"墙钟慢但质量行", **非"质量差"**

**对 C 波**: 协作非"质量劣不可用", 而是"墙钟劣 (木桶) + 质量可". 产能决策:
- 简单批量: 协作优 (墙钟+质量双优)
- 思考性任务: 协作墙钟劣 (木桶), 但质量 OK → **看时间敏感度** (急→单 agent, 不急→协作可)

## harness 修复建议 (送 P86 §F)

Agent 工具 result 字段应回收 agent 最终完整输出 (非摘要). 现状:
- result 只放 "任务完成" 摘要
- 完整产出在 output_file (JSONL transcript)
- agent 调用方 (老王) 看到 result 空, 误判 agent 没产出

建议: result 字段回收 agent 最后 assistant message 的完整 text (或前 N 字).
这是 Claude Code 平台层, agent 无法自修, 送卡人类.

## Q2 状态
- ✅ harness bug 确认 (result 回收缺陷)
- ✅ 批次4 重判 (墙钟劣, 质量不劣)
- ✅ A2 定论修正 (协作"墙钟慢质量行", 非"质量差")
- 🔴 原批次4 batch4-independent-write.md "全空"结论需同步修正
