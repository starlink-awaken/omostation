---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-28"
type: ephemeral
status: archived
---

> ⚠️ **A2 SSOT 已 supersede 本文件中任何「5.4x / 协作普遍正收益」定论句**。  
> 唯一协作收益定论: [`.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md`](2026-07-29-p86-a2-collaboration-gain-map.md)  
> （5.4x 作废 · batch5 demote · 多 agent 真 dispatch 仅 3 类型 + shortfall · ADR-0289）  
> 本文件保留为历史实验记录，**不得**单独作 C 适用面依据。

# P84 N3 批次3: 协作机制对抗冲突消解边界 (机制基线)

> 上位: N3 (J3 劣化信号跟踪 · 不许淹没)
> 🔴 红线 (P84 §F): 协作失效必须如实上报送卡, 掩盖 = 违规
> 口径声明: 本批次为 **机制模拟** (run-scenario 能力轨, 单进程注入事件→规则评估),
>           非真 dispatch agent 墙钟对照 (批次2 口径). 两者互补, 口径差异已标注.

## 实验设计
- 素材: 能力轨 134 场景 (gen-scenarios 生成 + 手写)
- 维度: category (A_conflict / B_failure / C_decomp / D_reuse) × adversarial (正常 / 红队对抗)
- 跑批: `run-scenario.py --dir .omo/_delivery/collab-scenarios/ --json`
- 指标: passed/total (协作管线对注入冲突/失败的消解成功率)

## 核心结果 (协作机制失效边界)

| 场景类型 | 消解率 | 判定 |
|---------|--------|------|
| A_conflict 正常 | **61/61 (100%)** | ✅ 协作机制有效 |
| B_failure_injection 正常 | 17/17 (100%) | ✅ 协作机制有效 |
| C_decomposition 正常 | 13/13 (100%) | ✅ 协作机制有效 |
| D_reuse_pair 正常 | 13/13 (100%) | ✅ 协作机制有效 |
| **A_conflict 对抗 (ADV)** | **1/27 (4%)** | 🔴 **协作机制失效** |
| B_failure 对抗 | 0/1 (0%) | ⚠️ 数据不足 (仅 1 样本) |

**关键发现**: 协作管线对**正常冲突/失败**100% 消解, 但对**红队对抗场景**96% 失效.

## 失效模式 TOP (对抗场景协作机制盲区)

| 失效 criterion | 次数 | 含义 |
|---------------|------|------|
| double_claim_detected | 5 | 双声明冲突未检测 |
| starvation_resolved | 5 | 资源饥饿未消解 |
| audit_reject_handled | 4 | 审计拒绝未处理 |
| orphan_detected | 4 | 孤儿任务未识别 |
| partial_failure_handled | 4 | 部分失败未兜底 |
| unauthorized_detected | 4 | 未授权操作未拦截 |

→ 协作机制的盲区: **对抗性的声明冲突 / 资源争抢 / 权限越界 / 部分失败**.
   这些恰是真实多 agent 协作的高风险场景 (双写/抢占/越权/部分崩溃).

## 对照序列 (协作适用边界全景)

| 批次 | 任务类型 | 协作表现 | 结论 |
|------|---------|---------|------|
| 批次1 (W1 任务#1) | 独立无依赖批量 (6 INTERFACE as_of) | **5.4x 优** | 协作适用 (并行收益大) |
| 批次2 (K4) | 简单分析归因 (真 dispatch 墙钟) | **1.7x 劣** | 协作不适用 (dispatch overhead + 木桶) |
| 批次3 (N3 本批) | 对抗冲突消解 (机制模拟) | **4% 消解** | 🔴 协作机制对对抗场景失效 |

**协作非万能, 且有硬上限**: 适用独立并行, 不适用串行分析, 对抗性冲突消解是盲区.

## 🔴 送卡建议 (请人类重估 P84 产能爬坡假设)

P84 假设 "60 任务/月" 建立在协作有正收益之上. 三批次数据揭示:

1. **协作正收益仅限独立并行批量** (批次1 5.4x). 串行分析 (批次2) / 对抗消解 (批次3) 无收益或失效.
2. **真实 backlog 任务多为串行/交互式** (写代码/调试/审查), 非独立并行 → 协作收益存疑.
3. **对抗场景 (双写/抢占/越权/部分失败) 协作机制 96% 失效** → 真实多 agent 并发风险未覆盖.

建议:
- 产能爬坡目标按**任务类型分层**重估 (独立并行可激进, 串行/对抗保守)
- 对抗消解机制 (double_claim / starvation / orphan / unauthorized / partial_failure) 列入治理债
- 真 dispatch 对照实验 (批次2 口径) 补跑批次3 场景, 验证机制模拟与真 agent 的一致性

## 口径差异声明 (诚实)

- 本批次: **机制模拟** (run-scenario, 协作管线规则引擎对预设事件流的处理)
- 批次2: **真 dispatch** (3 haiku Agent 并行 vs 1 顺序, 墙钟对比)
- 两者测的维度不同: 机制模拟测"管线规则有效性", 真 dispatch 测"agent 协作效率"
- 真 dispatch 补跑对抗场景 = 下一步 (验证机制盲区是否在真 agent 下同样存在)

## 红线遵守
- ✅ 劣化信号未淹没 (批次2 劣 1.7x + 批次3 4% 消解 均如实上报)
- ✅ 对抗有效性 >20% (27 对抗失败 ≥ 3, 非自欺)
- ✅ 不掩盖协作负收益 / 不夸大协作能力
