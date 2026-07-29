---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: "2026-07-29"
---
# P86 A2 协作收益地图 (定论 · SSOT)

> 上位: P86 §A2 · human-delegated D2 · ADR-0247 amend  
> 🔴 红线: 只记**真 dispatch**；禁止与机制模拟混成单一数字；禁类型间平均  
> 状态: **✅ 4/4 类型已测 (真 dispatch) — 定论**  
> A1: `.omo/standards/collab-task-taxonomy.md`  
> A3: `.omo/_knowledge/audits/2026-07-29-p86-a3-completion-rootcause.md`

## 定论表 (≥4 类型 · 真 dispatch)

| # | 任务类型 (A1) | 协作墙钟 | 单 agent 墙钟 | 协作收益 | 质量 | 证据路径 |
|---|---------------|---------|---------------|---------|------|----------|
| 1 | independent + none + well_defined + few | 快 | 慢 | **优 5.4x** | 优 | 历史 INTERFACE as_of 批次1 (真 dispatch) |
| 2 | ordered + read + well_defined + few | 223s | 128s | **劣 1.7x** | — | 失败归因 R/S/C 批次2 |
| 3 | coupled + write + negotiated | 115s | 140s | 墙钟优 18% | **劣 (1/3 有效)** | [batch3](2026-07-29-p86-a2-batch3-coupled-write.md) |
| 4 | independent + write (思考性设计) | 190s | 110s | **墙钟劣 73%** | 不劣† | [batch4](2026-07-29-p86-a2-batch4-independent-write.md) + [Q2](2026-07-29-p86-q2-harness-bug-falsification.md) |

† Q2: harness `result` 空属回收 bug；`output_file` 证实 3/3 有实质方案。墙钟劣 (木桶) 仍成立。

**禁止混算**: 上表四行**不得**合成「平均协作收益 X」；适用面决策只读分类行。

## 定论一句话

协作正收益**仅在「简单独立批量」** (批次1: independent + none/read + well_defined) 证实。  
分析 / 方案设计 / 思考性独立写 → 墙钟劣或质量劣或双劣。

## 对 C 波 / ADR-0247 的约束

| 场景 | 是否走协作管线 |
|------|----------------|
| 简单独立批量 (as_of / 机械批量) | ✅ 可用 |
| 分析 / 方案 / 审查 / 调试 | ❌ 单 agent 直做 |
| 物理依赖 / 人类红线 | ❌ 协作无用 (见 A3) |

产能月目标 **15** 真实任务 (D2)，完成率 ≥85%；旧 30→45→60 **作废**。

## A1 / A3 交叉

- **A1** 四维预测: independent+well_defined 强正 ✅；ordered 弱/负 ✅；coupled+write 负/质量差 ✅；independent 不保证优 (批次4 反转难度维) ✅  
- **A3**: 未完成任务 **0** 归因协作缺陷 → 产能瓶颈非管线，目标须分层而非「协作越多越好」

## 熔断遵守

- ✅ 未只跑有利类型  
- ✅ 未混模拟/真 dispatch  
- ✅ 禁平均  
- ✅ 本关闭 PR **不**开启 wave32+ ADV 传送带
