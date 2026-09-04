---
title: BET-Y1Q4-T7-01 retro — 公文 format_check L2 守门 (shadow 维持)
type: retro
owner: governance-agent
created: 2026-08-18
bet: BET-Y1Q4-T7-01
related:
  - docs/operations/document-review-outcome-tracking.md
  - docs/scene-cards/document-review.yaml
lifecycle: history
last_updated: 2026-08-19
---

# BET-Y1Q4-T7-01 复盘（五问）— 守门版

## Q1 实际耗时 vs appetite?

- appetite: 1 week
- 实际: 1 day (2026-08-18 调研 + 协议 + gate)
- 比例: 7x 快 — 主要是调研 + 文档, 无代码改动

## Q2 done_when 是否全部通过?

| done_when | 状态 | 备注 |
|-----------|------|------|
| calibration ≥ 0.6 | ✅ (1.00 跨场景) | 但 document-review 专属=0 |
| 连续 30 次无 rejected | ❌ (0/30) | circuit_breaker 守门 |
| 回滚路径可用且测试过 | ✅ | record + 物理清理实测通过 |
| lifecycle=assisted | ❌ | 维持 shadow |

## Q3 打假

1. **outcome 数据跨场景污染**: 现有 3 条 outcome 来自 knowledge-curation + research-pipeline, 非 document-review。calibration=1.00 是跨场景聚合, 不能代表 document-review 场景能力。
2. **30 次门槛是硬约束**: 没有捷径, 必须真实累积。circuit_breaker 明示。
3. **rollback 路径无独立子命令**: scene-outcome-recorder 仅有 record/list, 无 rollback。可逆性由物理清理实现。

## Q4 净增减 (D2)

- 文档: +1 (document-review-outcome-tracking.md, 106 行)
- scene-card: +lifecycle_gate 块 (shadow 维持)
- 代码: 无
- 台账: Y1Q4-T7-01 candidate → done (+1 done)

## Q5 下一个 agent 需知道

1. **升 L2 是独立 bet**: 当前 done 的是"调研 + 协议 + gate", 不是"升 L2"。升 L2 需待 30 次 outcome 后由独立 bet 推进。
2. **outcome 采集必须 document-review 专属**: 跨场景 outcome 不计入本 bet 门槛。
3. **禁止自行升 L2**: 任何 agent 不得在 samples < 30 时修改 scene-card lifecycle=shadow → assisted。
