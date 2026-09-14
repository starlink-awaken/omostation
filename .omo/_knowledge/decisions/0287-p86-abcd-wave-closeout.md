---
id: ADR-0287
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-07-29
related:
  - 0247-strategic-pivot-collab-first-physical-deferred.md
  - 0249-governance-budget-cap-40-40-20.md
type: ssot
---

# ADR-0287: P86 A/B/C/D 波关闭 + §STOP 冻结

## Context

P86 长计划要求关闭协作再评估四波；并发 session 曾继续 ADV 传送带至 wave31，
与 longplan §STOP / B1' 冲突。本 ADR **关闭 ABCD**，并**冻结**场景增长门，
**不**开启 wave32+ 自动检测器/加硬循环。

## Decision

1. **A**: 协作收益地图 4 类型真 dispatch 定论为 SSOT（简单独立批量唯一正收益）。
2. **B**: 已设计类计入 ≥60% 分母；仅对抗/真实 0 类显式 **unsupported**；不为构造补实现。
3. **C**: 月真实任务 15、完成率 ≥85%、协作仅简单独立批量；旧 30/45/60 作废；amends ADR-0247。
4. **D/§STOP**: `check-scenario-growth` 对无 `real_occurrence_evidence` 的**新增** ADV blocking；
   stock grandfather + ADV_CAP/detector baseline 冻结于 2026-07-29 关闭点。
5. **Non-goal**: 本决策不授权 E1 破坏性 revert、D4 四项、ADV 自动扩面。

## Status

**ACCEPTED** 2026-07-29.
