---
id: ADR-0259
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-07-29
related:
  - 0256-p84-w3-throughput-wave.md
  - 0258-p84-w3-wave3-tooling-hygiene.md
  - 0254-p84-w22-cclass-collab-detectors.md
---

# ADR-0259: W3 wave4 — ADV13/15/17 检测 + patterns 注册 + 产能 gap 收口

## Decision

1. **能力轨**: scenario_lib 补 `collusion_detected` / `priority_inversion_detected` /
   `cascade_failure_contained`（ADV13/15/17 闭环）。**同时**加硬 ADV19/21/23
   （byzantine_quorum / replay / cross_key_collusion）— 管线未实现 → 诚实 FAIL，
   满足 P84「全过=自欺」与 `check-adversarial-effectiveness` 门禁。
2. **治理面**: 注册 `.omo/patterns/` 为 `OMO-PATTERNS` top-level asset（消 interface-check
   unregistered patterns）。
3. **工程债盘点**: `bos-stdio-inventory.py` 只读统计 stdio-ish 比（禁止标签假迁移）。
4. **产能轨**: 本波真实 done 记账，目标 gap→0（≥30）；禁止空卡。

## Status

**ACCEPTED** 2026-07-29.
