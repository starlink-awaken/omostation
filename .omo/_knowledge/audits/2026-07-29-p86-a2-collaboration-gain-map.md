---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---

> 📌 **唯一协作收益定论 SSOT**（冷启动请只读本文件；旧 audit 中 5.4x 表已 supersede）。

# P86 A2 协作收益地图 (多 agent 真 dispatch 定论)

> 上位: P86 §A2 · R1 重判 · human-delegated D2 · skeptic demote type1  
> 🔴 红线: **真 dispatch** = 协作管线/多 agent vs **单 agent** 墙钟/质量对照；禁止把 `scenario_lib` 线程池微基准冒充协作适用面证据  
> A1: `.omo/standards/collab-task-taxonomy.md`  
> A3: `.omo/_knowledge/audits/2026-07-29-p86-a3-completion-rootcause.md`  
> R1: `.omo/_knowledge/audits/2026-07-29-p86-r1-a2-rejudgment-outputfile.md`

## ⛔ 作废 / 降级

| 项 | 原因 | 处置 |
|----|------|------|
| **5.4x** | R1: 非等量、无严谨墙钟 | **禁止**作定论/C 依据 |
| **batch5 1.65x** | ThreadPool × `run_scenario` 微基准，**非** haiku/多 agent 真 dispatch | **降级**为机制微基准附录；**不得**支撑「多 agent 协作适用面」 |

## Shortfall（诚实）

验收原文要求 ≥4 类型各有**多 agent 真 dispatch**。当前可审计的多 agent 真 dispatch **仅 3 类**（下表 2–4）。  
类型1（简单独立批量）在剔除 5.4x 后**无**多 agent 真 dispatch 墙钟对 → **shortfall 记档**，不伪造第四类。

## 定论表 — 多 agent 真 dispatch（3 类型）

| # | 任务类型 (A1) | 协作墙钟 | 单 agent 墙钟 | 墙钟收益 | 质量/产出 | 审计 (on-disk) |
|---|---------------|---------|---------------|---------|-----------|----------------|
| 2 | ordered + read + well_defined | **223s** | **128s** | 劣 **1.7x** | 产出量未纯 text 复验 | [R1 §batch2](2026-07-29-p86-r1-a2-rejudgment-outputfile.md) |
| 3 | coupled + write + negotiated | **115s** | **140s** | 墙钟优 18% | 纯 text 协作 **0.6x** | [batch3](2026-07-29-p86-a2-batch3-coupled-write.md) · [R1](2026-07-29-p86-r1-a2-rejudgment-outputfile.md) |
| 4 | independent + write (思考性) | **190s** | **110s** | 劣 **73%** | 纯 text 协作 **0.5x** | [batch4](2026-07-29-p86-a2-batch4-independent-write.md) · [R1](2026-07-29-p86-r1-a2-rejudgment-outputfile.md) · [Q2](2026-07-29-p86-q2-harness-bug-falsification.md) |

**禁止混算** 三行为单一平均。

### 定论（仅上表）

在已测的**思考性/有序/耦合** 多 agent 真 dispatch 上，协作相对单 agent **不占优**（墙钟和/或纯 text）。  
**C 波「协作仅简单独立批量」适用面** 依据：

1. **human-delegated D2**（人类授权）  
2. 上表 2–4 **负证据**（思考性不默认协作）  
3. **不**依据 5.4x；**不**依据 batch5 线程池微基准作为多 agent 证明  

简单独立批量：人类 D2 允许使用协作管线；**多 agent 墙钟正收益尚未用真 dispatch 闭环**（待人类派单重跑等量 multi-agent 对照）。

## 附录 — 机制微基准（非真 dispatch · 不入 C 适用面分子）

| 实验 | 方法 | 墙钟 | 可声称 |
|------|------|------|--------|
| batch5 | ThreadPool 并行 vs 顺序 `run_scenario` 三 ADV | 0.019s vs 0.032s | **仅**「等量独立单元可并行加速 scenario runner」；**非**多 agent 协作管线收益 |

详见 [batch5](2026-07-29-p86-a2-batch5-simple-independent-equal-work.md)（文首已标 demote）。

## A1 / A3

- A1: ordered/coupled/thinking 与上表一致；independent+well_defined 多 agent **未闭环**  
- A3: 未完成 0 归因协作缺陷  

## 熔断

- ✅ 5.4x 剔除  
- ✅ batch5 不冒充真 dispatch  
- ✅ shortfall 显式（3/4 多 agent 类型）  
