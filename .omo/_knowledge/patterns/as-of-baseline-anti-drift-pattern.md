---
category: patterns
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-27
type: ssot
---

# Pattern: as_of 基线锚点（治理方案防脱钩）

> 承接 P73 decl-exec-gap 家族。防止"第五份方案"再次脱钩的治本项。
> 来源: integrated-governance-master-workorder §P0-D (2026-07-27)。

## 问题（decl-exec-gap 变体）

治理方案（proposal/plan）写完后的 24-48 小时内, workspace 被其他 agent 执行大量 P0 修复。
方案里的"现状描述"快速过期 → 后续 agent 凭方案的旧状态判断 → 误判（报"X 缺失"其实已修 / 报"X 存在"其实已删）。

这是 **decl-exec-gap 的时效变体**: 声明（方案）与执行（实际 workspace）的时间差导致脱钩。

## Pattern: as_of 基线锚点

**所有治理方案（proposal/plan/workorder）必须带 `as_of: YYYY-MM-DD` 基线锚点**, 标注:
1. **as_of 日期**: 方案"现状描述"的截断时间
2. **执行前必须**: 对照最新 workspace 核实, 勿凭方案旧状态判断
3. **已变化项附录**: 方案落地后, 追加"已变化项"指向实际落地点

## 何时触发

- 写新治理方案（proposal / plan / workorder）→ **必须**带 as_of
- 方案被引用为决策依据 → **必须**核实 as_of 是否过期
- agent 凭方案判断 workspace 状态 → **必须**对照 as_of + 实际核实（P73 truth-driven）

## 反模式（禁止）

- ❌ 方案无 as_of → 后人无法判断"现状描述"截断时间
- ❌ 凭方案旧状态判断, 不核实实际 workspace（P73 D1 凭路径直觉判存在性）
- ❌ 方案落地后不追"已变化项"附录 → 脱钩持续累积

## 关联

- P73 truth-driven-engineering-pattern（decl-exec-gap 家族本源）
- integrated-governance-master-workorder §P0-D（本 pattern 的落地工单）
- 三份子方案 as_of 附录（2026-07-27）: metaos / mof-m4 / l2-engines

## Enforcement

方案模板（proposal/plan）的 frontmatter 应含 `as_of:` 字段。doc-ssot-lint 或 governance check 可校验（后续 Phase, 非 P0）。
