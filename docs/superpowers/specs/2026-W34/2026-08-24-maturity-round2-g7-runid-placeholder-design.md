---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last-reviewed: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-07
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G7: Droid-Shield run-id 误报治理

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-07
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G7)

## 背景与问题

Droid-Shield 的 workspace 级拦截会对文档中出现的 run-id 格式字符串（如
`20260824T102541Z-governance-audit-d4e3ea25`）误报，把"文档示例/占位符"当作真实
run-id 拦截（CONV-3 被堵实证）。治理文档（spec、closeout、复盘）常写 run-id 示例，
导致无谓的 workflow 误报。

## 架构选择

在 `docs/operations/engineering-golden-rules.md` 新增 **RUN-ID-PLACEHOLDER** 铁律：
治理文档写 run-id 必须用占位符（如 `<run-id>`、`<timestamp>-<workflow>-<hash>`），
不写真实格式的完整字符串；确需引用真实 run-id 时显式标注（`runtime fact`）。
这从规范层避免 Droid-Shield 对文档示例的误报。

## 验收标准

1. **[engineering-golden-rules 含 RUN-ID-PLACEHOLDER 规则]**
   - 验证方式：grep "RUN-ID-PLACEHOLDER" docs/operations/engineering-golden-rules.md
   - 证据类型：规则存在且含占位符示例

## 反指标

- 不改 Droid-Shield 拦截逻辑（那是平台层，规范先行）
- 不追溯历史文档（只约束新写）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 规范 vs 改拦截器 | 规范入 golden-rules | 平台层拦截逻辑不可控, 规范是立即可行的治本 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G7) | agent |
