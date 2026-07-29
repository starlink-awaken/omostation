---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-29
related:
  - 0256-p84-w3-throughput-wave.md
  - 0258-p84-w3-wave3-tooling-hygiene.md
  - 0254-p84-w22-cclass-collab-detectors.md
---

# ADR-0259: W3 wave4 — ADV13/15/17 检测 + patterns 注册 + 产能 gap 收口

## Decision

1. **能力轨**: scenario_lib 补 `collusion_detected` / `priority_inversion_detected` /
   `cascade_failure_contained`（ADV13/15/17），对抗集 33/33 通过（全过时仍须保持对抗强度，
   后续可增 red-team 场景，非本 ADR 放宽判定）。
2. **治理面**: 注册 `.omo/patterns/` 为 `OMO-PATTERNS` top-level asset（消 interface-check
   unregistered patterns）。
3. **工程债盘点**: `bos-stdio-inventory.py` 只读统计 stdio-ish 比（禁止标签假迁移）。
4. **产能轨**: 本波真实 done 记账，目标 gap→0（≥30）；禁止空卡。

## Status

**ACCEPTED** 2026-07-29.
