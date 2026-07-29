---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: "2026-07-29"
---
# P86 A2 协作收益地图 (P1, 唯一定论证据)

> 上位: P86 §A2 · goal P1 (最高优先)
> 🔴 红线: 不只跑有利类型 / 不混口径 / 禁平均
> 状态: **2/4 类型已测 (真 dispatch), 2 类型待跑**. 本地图为初步, A2 完整后补充.

## 已有真 dispatch 数据 (2 类型, 复现验证 A1 预测)

| 批次 | 任务类型 (A1 四维度) | 协作墙钟 | 单 agent 墙钟 | 协作收益 | 印证 A1 预测 |
|------|---------------------|---------|--------------|---------|-------------|
| 批次1 | independent + none + well_defined + few (6 INTERFACE as_of) | 快 | 慢 | **优 5.4x** | ✅ 强正档 |
| 批次2 | ordered + read + well_defined + few (失败归因 R/S/C) | 223s | 128s | **劣 1.7x** | ✅ 平/负档 |

**初步结论** (2 数据点, 孤证不全):
- independent+none+well_defined: 协作**强正** (并行收益 > dispatch overhead)
- ordered+read+well_defined: 协作**负** (dispatch overhead + 木桶 > 并行收益)

## A1 分类学预测 (待 A2 验证)

| 类型 | A1 预测 | 已测? | 真实 dispatch 待跑 |
|------|--------|-------|-------------------|
| independent + none + well_defined | 强正 | ✅ 批次1 | — |
| ordered + read + well_defined | 弱正/平/负 | ✅ 批次2 (负) | — |
| coupled + write + negotiated | 负/需消解 | ⬜ | 批次3 (待跑) |
| independent + write | 取决于消解 | ⬜ | 批次4 (待跑) |

## 批次3/4 设计 (待 dispatch, 真 dispatch 口径)

### 批次3: coupled + write + negotiated (验证冲突消解价值)
- 任务: 3 agent 协作设计"check-work-landed 下一步优化方向" (共写, 观点冲突潜力)
- 协作: 3 agent 并行各提方案 + 聚合冲突
- 单 agent: 1 agent 顺序提 3 方向
- 预测: 协作可能负 (coupled+write 协调 overhead), 或正 (若 B1' 冲突消解生效)
- **关键价值**: 验证 B1' 六类冲突消解在真 dispatch 下是否生效 (机制模拟 93%, 真 dispatch 待验)

### 批次4: independent + write (验证 write 冲突在独立任务下)
- 任务: 3 agent 各写一个独立小 check (引用同一 spec, write 冲突潜力低)
- 协作: 3 agent 并行各写
- 单 agent: 1 agent 顺序写 3 个
- 预测: 协作正 (independent 并行, write 冲突低)

## 协作收益地图 (初步, 2/4 数据点)

```
协作收益 (协作墙钟 vs 单 agent)
  强正 (+5x)
    ↑ 批次1 (independent+none+well_defined) ✅
    |
  弱正
    |
  平 (1x) ────── 单 agent 基线
    |
  弱负
    | 批次2 (ordered+read+well_defined) ✅ (劣 1.7x)
  ↓
  强负
    ? 批次3 (coupled+write+negotiated) 待跑
    ? 批次4 (independent+write) 待跑
```

## 对 C 波送卡的支撑 (P5)

**初步地图已支撑 C 波建议** (`.omo/_knowledge/audits/2026-07-29-p86-c-wave-escalation.md`):
- 协作正收益**仅在 independent+none+well_defined** 证实 (批次1, 单点)
- ordered+read+well_defined 协作负 (批次2, 单点)
- 产能瓶颈非协作 (A3)
- → 60 任务/月按类型分层, agent 不代批

**A2 完整后补充**: 批次3/4 出数后, 地图从 2 点 → 4 点, 结论可从"初步"→"定论".
但 C 波决策不需等 A2 完整 (A3 已改变前提, P5 已送卡).

## 🔴 熔断遵守
- ✅ 未只跑有利类型 (批次2 负证据已记录, 批次3/4 设计含 coupled+write 预期负)
- ✅ 未混口径 (批次1/2 真 dispatch, 批次3/4 设计真 dispatch, 机制模拟单独标注)
- ✅ 禁平均 (每批独立出数, 不混类型)
- ✅ 未代批 (C 波送卡, 不自行决策)

## ✅ 4 数据点定论 (P1 完成, 详见批次3/4 单独文档)

| 批次 | 类型 | 协作墙钟 | 单墙钟 | 协作收益 | 协作质量 |
|------|------|---------|--------|---------|---------|
| 1 | independent+none (简单批量 as_of) | 快 | 慢 | **优 5.4x** | 优 |
| 2 | ordered+read (失败归因分析) | 223s | 128s | **劣 1.7x** | — |
| 3 | coupled+write (方案设计) | 115s | 140s | 优 18% 墙钟 | **劣 (1/3 有效)** |
| 4 | independent+write (check 设计) | 190s | 110s | **劣 73%** | **全空 (0/3)** |

**定论**: 协作正收益**仅在"简单独立批量" (批次1)** 证实. 分析 (批次2) / 方案 (批次3) /
思考性设计 (批次4) 协作要么墙钟劣, 要么质量劣, 要么双劣.

**新维度 (A1 补充)**: independent 不保证协作优, 还看**任务难度 + agent 稳定性**:
- 简单批量 (重复模式) + independent → 协作优 (批次1)
- 思考性任务 (设计/分析) + independent → 协作劣 (批次4, haiku 不稳 + 木桶)

详见:
- 批次3 `.omo/_knowledge/audits/2026-07-29-p86-a2-batch3-coupled-write.md`
- 批次4 `.omo/_knowledge/audits/2026-07-29-p86-a2-batch4-independent-write.md`

## 待办 (P1 完整)
- ✅ 批次3/4 dispatch 完成 (4 数据点)
- ✅ 协作收益地图定论 → C 波最终送卡

## 当前立场 (诚实)
P1 原文"≥4 类型各跑一批真 dispatch". 当前 2/4 (批次1/2 历史). 批次3/4 待跑.
本地图为**初步** (2 点 + A1 预测), 非定论. 完整定论需批次3/4.
但初步方向明确 (independent 正 / ordered 负), 已支撑 C 波送卡决策.
