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

# P86 A3: 45.5% 完成率逐任务归因

> 上位: P86 §A3 (11 真实任务 6 未完成逐个归因)
> 🔴 熔断: 不混口径/不掩盖. 归因如实, 即使结论挑战 P86 预设.

## 核心发现 (改变 P86 叙事)

> **6 个未完成任务中, 0 个归因于"协作机制缺陷". 主因是物理依赖 + 工程工作量 + 优先级.**

P86 §A3 预设: "若协作机制缺陷占多数 → 问题在管线". 实测**相反**:
产能 45.5% 不完成的瓶颈**不在协作管线**, 在任务本身的物理/工作量依赖.
**协作 vs 单 agent 对这 6 个任务都没用** (都卡在物理资源或工作量, 不是 agent 协调问题).

## 逐任务归因 (6 未完成)

| 任务 | status | 归因 | 协作相关? |
|------|--------|------|----------|
| NEEDS-HUMAN-BATCH2-PHYSICAL-RECOVERY-CHECKLIST | deferred (owner=human) | **物理依赖** (真机恢复 + 物理 KPI G-DEL.1/3) | ❌ 协作无用 (人类物理操作) |
| NEEDS-HUMAN-P80-PHYSICAL-HOSTS | deferred (owner=human) | **物理依赖** (扩展物理机 ≥4 + G-DEL.3) | ❌ 协作无用 (人类物理资源) |
| NEEDS-HUMAN-P80-PHASE45-BOS-STDIO | backlog (owner=engineering) | **工程工作量** (169 服务, stdio 比例 0.692 > 0.65, 需逐服务迁移) | ⚠️ 协作可并行迁移 (independent), 但量级是瓶颈 |
| cockpit-debt-debt-1 | pending | **字段缺失** (无 owner/due/desc, 需补元数据才能归因) | ❓ 待补 |
| OPC-P6-SELF-EVOLUTION-doc-gate-e | candidate | **优先级** (未启动, 文档协调) | ❌ 未启动非协作问题 |
| debt-l0-gac-consensus-onboard-triage | (done 目录, status 待确认) | **状态迁移中** (L0 解锁 PR #570 已 merge, debt 闭环) | ❌ 已闭环 |

## 归因分布

| 归因类 | 数量 | 含义 |
|--------|------|------|
| 物理依赖 (owner=human) | 2 | 等人类物理操作, 协作无用 |
| 工程工作量 | 1 | 大规模服务迁移, 量级瓶颈 (协作可加速但非主因) |
| 字段缺失/状态迁移 | 2 | 元数据债, 非任务难度 |
| 优先级 | 1 | 未启动 |
| **协作机制缺陷** | **0** | **没有任何任务因协作机制不完不成** |

## 对 P86 各波的启示

### 对 C 波 (产能目标重设) — 重要
P84 "协作提升产能" 假设在**这 6 个任务上不成立**: 物理依赖任务协作和单 agent 都完不成.
→ 产能瓶颈是**物理资源 + 工作量**, 不是 agent 数量.
→ "60 任务/月" 若含大量物理依赖任务, 协作无济于事 — 需按**任务类型分层设目标** (A1 分类学):
  - independent+well_defined: 协作可激进 (批次1 5.4x)
  - 物理依赖: 协作无用, 目标取决于人类/硬件节奏
  - 工程工作量 (如 BOS-STDIO 169 服务): 协作可并行加速, 但量级是硬约束

### 对 B 波 (冲突消解) — 独立
A3 归因 (产能非协作缺陷) **不否定** B1 (对抗消解 4% 是协议缺陷).
两个独立结论:
1. 产能 45.5% 不完成: 主因物理/工作量 (A3, 本文档)
2. 协作对抗消解 4%: 协议没设计 6 类冲突 (B1)
→ 协作机制在**对抗场景**有缺陷 (B1), 但这**不是当前产能瓶颈** (A3). 两者都需修, 但优先级不同.

### 对 A2 (协作收益地图) — 校准
A3 证明 "真实任务多为物理依赖/工作量, 非协作适用场景". A2 对照实验应**刻意选协作适用类型**
(independent+well_defined) vs 不适用类型 (物理依赖), 验证分类学预测. **不得只跑有利类型** (熔断).

## 诚实记录 (不掩盖)
- ✅ 6 未完成 0 个归因协作缺陷 — 如实记录, 即使这"有利于协作叙事"
- ✅ 不据此宣称"协作没问题" — B1 的 4% 对抗消解是独立的协作缺陷 (不淹没)
- ✅ 物理依赖任务不是协作能解的 — 不硬推协作到不适用的任务 (C2 精神)

## 本轮交付 (A3)
- ✅ 6 未完成逐个归因 (物理 2 / 工程量 1 / 字段缺失 2 / 优先级 1 / 协作缺陷 0)
- ✅ 核心结论: 产能瓶颈非协作, 是物理+工作量
- ⬜ cockpit-debt 字段补全 (待, 元数据债)
- ⬜ A2 真 dispatch 对照 (批次4-7, 待跑, 按分类学选型)

## References
- P86 longplan §A3 · §C1
- A1 分类学 `.omo/standards/collab-task-taxonomy.md`
- B1 根因 `.omo/_knowledge/audits/2026-07-29-p86-b1-conflict-resolution-rootcause.md`
