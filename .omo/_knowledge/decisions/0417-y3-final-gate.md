---
id: ADR-0417
title: Y3 终局门 — 三年验收标准判定（BET-Y3H2-T1-02）
status: archived
lifecycle: spec
owner: 夏明星
created: 2026-08-18
last_updated: 2026-08-18
deciders:
  - 夏明星 (最终确认)
  - governance-agent (起草)
related:
  - .omo/_knowledge/decisions/0415-reject-agt-integration-adopt-capability-parity.md
  - .omo/_knowledge/decisions/0416-y2-gate-vision-falsification.md
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
---

# ADR-0417: Y3 终局门 — 三年验收标准判定

## Context

按 [BET-Y3H2-T1-02](../../../docs/plans/3y-bet-ledger.yaml) 要求，对三年规划三条验收标准做最终判定。源材料：[三年规划 §2.2 三年后可验收状态](../../../docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md)。

## 三条验收标准（原文）

1. **每周 ≥ 5 条主动产出被采纳**，采纳率 ≥ 40%。
2. **本人修订率逐年下降**：Y1 基线 → Y2 降 20% → Y3 降 40%。
3. **可持有性守住**：已识别冗余全部清零（知识层双头、无消费者模块、无违规历史的 required 规则、零调用脚本、休眠项目），且保护量未被牺牲（`test_loc` 不低于基线、ADR 文件总数不减少）。

## 判定

> **当前时间点（2026-08-18）距 Y3 终局（2029-06）尚有 2.5 年，本次判定为"中期校准"而非终局判定。**

| # | 标准 | 中期证据 | 风险 |
|---|------|---------|------|
| S1 | 周产出 ≥ 5 条采纳 | 无系统化的建议→采纳记录链路（同 ADR-0416 P1）；当前可见产出集中在治理层（ADR/commit），缺少"主动建议→被采纳"的显式证据 | 高 — 若度量不建立，2029 年无法判定 |
| S2 | 修订率逐年降 | Y1 基线未建立（同 ADR-0416 P2） | 高 — 无基线则 Y2/Y3 无法对比 |
| S3 | 可持有性守住 | 部分达成：runtime/cockpit/agora 承重且健康；gbrain×kairon 双头未合并；family-hub/observability 休眠未清理；零调用脚本未全清 | 中 — 有清单可执行 |

## Decision

1. **不触发终局关停**：Y3 尚有 2.5 年，当前证据不足以判定失败。
2. **S1/S2 度量建设为最高优先级**：绑 BET-Y2Q1-T3-02（意图模型接 goals/tasks），3 周内建立"建议→采纳"记录链路 + 修订率基线。
3. **S3 按清单推进**：
   - 知识层双头（gbrain × kairon）→ 2027 Q1 评估合并窗口
   - 休眠项目（family-hub/observability）→ 归档或删除（1 周内）
   - 零调用脚本 → 扫 `bin/` 标 last-accessed，批量清

## Consequences

- 2027-12-31 做第一次正式门评审（ADR-0416 已定）
- 2029-06 做终局判定（本 ADR 届时重审）
- 若 S1/S2 度量在建后 8 周无改善 → 触发收窄评估

## References

- [三年规划 §2.2](../../../docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md)
- [ADR-0416 Y2 门](./0416-y2-gate-vision-falsification.md)
- [BET-Y3H2-T1-02 goal](../../../docs/plans/3y-bet-ledger.yaml)
