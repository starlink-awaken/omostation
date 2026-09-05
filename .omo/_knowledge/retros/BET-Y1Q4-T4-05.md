---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-05
---
# Retro: BET-Y1Q4-T4-05 — Spine Done 价值证明债清册与抽样回填

## 1. What went well

- 系统性扫描了全部 290 个 done bet，产出了结构化债清册
- 发现 90% 的 value debt 是结构性的（vip=false by design），不是遗漏
- 对 5 条 T4-OUTCOME 重要 bet 完成了抽样回填：4 条豁免 + 1 条回填为 PROVEN
- 债清册清晰区分了 "结构设计如此" vs "真正需要关注" 的债务

## 2. What went wrong

- 无。执行过程顺利。

## 3. Key learnings

- **Value indicator policy=false 是正确设计。** 大部分工程交付 bet 不直接产出用户价值，强制标注 value 证据会违反诚实原则。
- **T4-OUTCOME 是价值证明的核心轨道。** 所有非结构性 value proof 应集中在此轨道。
- **NOT_PROVEN 不等于失败。** 在没有足够样本量前，NOT_PROVEN 是最诚实的标注。

## 4. Action items

- [ ] 季度门时回顾债清册，检查是否有 bet 从 NOT_PROVEN 升级为 PROVEN 的机会
- [ ] 当 ≥50 条 adjudication 累积时，重新评估 BET-Y1Q3-T4-04 的 value 状态
- [ ] 当 ≥3 个 outbox consumer 存在时，重新评估 BET-Y1Q3-T4-06 的 value 状态

## 5. Metrics

- 扫描 bet 数: 290
- 价值债务数: 261 (90%)
- 结构性豁免: 255 (98%)
- 抽样回填: 5 (4 豁免 + 1 PROVEN)
- 产出文件: docs/reports/2026-09-05-value-proof-debt-registry.md
