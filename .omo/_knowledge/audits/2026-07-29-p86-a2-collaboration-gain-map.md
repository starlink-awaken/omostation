---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: "2026-07-29"
---
# P86 A2 协作收益地图 (定论 · 可审计墙钟)

> 上位: P86 §A2 · R1 重判 · human-delegated D2  
> 🔴 红线: 只列**可追溯审计 + 协作/单 墙钟数字对**；禁止与机制模拟混算；禁类型平均  
> 状态: **✅ 4 类型均有等量/真 dispatch 墙钟对**（**5.4x 已剔除**，见 R1）  
> A1: `.omo/standards/collab-task-taxonomy.md`  
> A3: `.omo/_knowledge/audits/2026-07-29-p86-a3-completion-rootcause.md`  
> R1: `.omo/_knowledge/audits/2026-07-29-p86-r1-a2-rejudgment-outputfile.md`

## ⛔ 作废数字

| 数字 | 原因 | 处置 |
|------|------|------|
| **5.4x** | R1: 非等量对照、无严谨墙钟/output_file、P81 估算 | **禁止出现在定论表**；不得支撑 C 适用面 |

## 定论表 (4 类型 · 墙钟对可审计)

| # | 任务类型 (A1) | 协作墙钟 | 单 worker 墙钟 | 墙钟收益 | 质量/产出备注 | 审计路径 (on-disk) |
|---|---------------|---------|----------------|---------|---------------|-------------------|
| 1 | independent + none + well_defined | **0.019s** | **0.032s** | 优 **1.65x** | 3/3 PASS (等量 3 单元) | [batch5](2026-07-29-p86-a2-batch5-simple-independent-equal-work.md) |
| 2 | ordered + read + well_defined | **223s** | **128s** | 劣 **1.7x** | 产出量未纯 text 复验 | [R1 §batch2](2026-07-29-p86-r1-a2-rejudgment-outputfile.md) |
| 3 | coupled + write + negotiated | **115s** | **140s** | 墙钟优 18% | 纯 text 协作 **0.6x** (单更深) | [batch3](2026-07-29-p86-a2-batch3-coupled-write.md) · [R1](2026-07-29-p86-r1-a2-rejudgment-outputfile.md) |
| 4 | independent + write (思考性) | **190s** | **110s** | 劣 **73%** | 纯 text 协作 **0.5x** | [batch4](2026-07-29-p86-a2-batch4-independent-write.md) · [R1](2026-07-29-p86-r1-a2-rejudgment-outputfile.md) · [Q2](2026-07-29-p86-q2-harness-bug-falsification.md) |

**禁止混算**: 四行不得合成单一「平均协作收益」。

## 定论一句话

1. **机械独立批量** (类型1 / batch5): 等量并行相对顺序有墙钟正收益 (1.65x)。  
2. **有序分析 / 耦合方案 / 思考性独立写** (类型2–4): 墙钟和/或纯 text 产出对单 worker **不占优**。  
3. **C 适用面** 依据: human D2 + 类型2–4 负证据 + 类型1 等量正证据；**不**依赖已作废 5.4x。

## 对 C / ADR-0247

| 场景 | 是否走协作管线 |
|------|----------------|
| 简单独立批量 (well_defined 机械单元) | ✅ 可用 (batch5) |
| 分析 / 方案 / 审查 / 调试 / 思考性写 | ❌ 默认单 agent (batch2–4 + R1) |

产能: 月 **15** 真实任务 · 完成率 ≥85% · 旧 30→45→60 **作废**。

## A1 / A3 交叉

- A1: independent+well_defined 可正 ✅ (batch5)；ordered 负 ✅；coupled/thinking 不占优 ✅  
- A3: 未完成 **0** 归因协作缺陷 → 产能瓶颈非管线

## 熔断

- ✅ 5.4x 已剔除  
- ✅ 每行含协作+单墙钟数字 + on-disk 审计链接  
- ✅ 未开 wave32+ ADV 传送带  
