---
status: active
lifecycle: history
owner: engineering-agent
bet: BET-Y1Q3-T4-02
last-reviewed: 2026-08-30
title: "Product P0 真值链收口报告: 六 WorkPacket 全 done (2026-08-30)"
type: report
---

# Product P0 真值链收口报告 (BET-Y1Q3-T4-02, 2026-08-30)

> 父 BET 编排六个独立 WorkPacket，收敛为可重放的 Product P0 真值链。
> 本报告是 T4-02 done_when 第 7 条 (回执齐全) 的收口交付。

## 1. 六 WP 终态

| WP | BET | 交付 | 终态 | 主仓锚点 |
|----|-----|------|------|----------|
| WP1 | T4-03 | Honest Scene Card Gate (`make scene-card-check` 诚实红) | done / delivery_accepted | #2380 链 |
| WP2 | T4-05 | Agent Cell Effect Receipt (admission/receipt/idempotency) | done / delivery_accepted | omo PR #118, canary `8d3f2765` |
| WP3 | T4-06 | Canonical Outbox Publisher (lease/retry 唯一) | done / delivery_accepted | omo PR #119 链 |
| WP4 | T4-04 | Principal Authority Binding (三端 digest 一致) | done / delivery_accepted | canary `a6aaca91` |
| WP5 | T4-07 | Human Adjudication → Principal-Bound Value | done / **outcome_accepted** | 真实裁决报告 `da896f8e` |
| WP6 | T4-08 | Physical Recovery Drill (隔离真实演练) | done / delivery_accepted | #2470 链 |

## 2. 价值真值链 (WP5 → 父 BET)

1. **real_signal**: corrosion-pipeline 对真实工作区探测产出的 3 条防腐信号
   (`MDEAD-HB-SYSTEM-HEALTH-YAML` 等)，经 canonical scene-card decision inbox
   登记 (scene `scene-*` / journey / intent `intent-a4369a2aff7c` 等，持久于
   `.omo/_inbox/`)。
2. **human_verdict**: principal:xiamingxing 对 3 条候选真实裁决 adopt×3；
   WP4 `DefaultPrincipalAuthority(production=True)` 权威验证产生 authority
   receipt digest；OMO truth-writer (`AdjudicationStore.record_wp5_outcome`)
   append-only 持久化 3 条 wp5-human-adjudication/v1 记录。
3. **episode lineage**: `PersonalEpisodeService` 在
   `runtime/omo/t4-07-sovereignty-ledger.db` 持久化 role/responsibility 指派
   (`role:human-principal` / `responsibility:decision-adjudication`) 与 3 个
   episode (`episode_98d211b7cb0a` 等)，request_id = intent id，幂等可重放。
4. **replay**: 同 adjudication_id 重放 → `replayed=true`，qualifying count 不变；
   fresh observer 回读 count=4 且 lineage 完整。
5. **attestation**: principal SSH 签名 (namespace `omostation-human-attestation`)，
   T4-07 与 T4-02 双回执均通过 `bet-ledger` 官方验签
   (`docs/operations/human-attestations/BET-Y1Q3-T4-07-accept.yaml` /
   `BET-Y1Q3-T4-02-accept.yaml`)。

## 3. 完成矩阵推导

engineering VERIFIED × operational PROVEN × value ACCEPTED
→ `overall_state: outcome_accepted` (value_indicator_policy=true)。

## 4. 回滚与停机

冻结新 adjudication，保留 append-only history，从 Event Ledger 重建 projection。
不改写已发生的人类裁决；lineage 不可证明或 Cockpit 绕过 OMO truth writer 时
立即停机 (circuit_breaker)。
